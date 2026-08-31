"""Leave request and approval routes (ring r2/people). Ported from
``app/modules/leave/routes.py``.

Email notifications on approve/reject wired via email.send_leave_status_email.
In-app notifications via platform ring kept.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.email import send_leave_status_email
from studioerp.errors import LeaveError
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.notifications.service import notify
from studioerp.platform.users import User
from studioerp.rings.people.leave import service as leave_service
from studioerp.rings.people.leave.schemas import (
    LeaveApplyRequest,
    LeaveBalanceOut,
    LeaveOut,
    LeaveRejectRequest,
    LeaveUserRow,
    TeamAvailabilityRow,
)
from studioerp.schemas import PaginatedResponse
from studioerp.time import now_local

router = APIRouter(prefix="/leaves", tags=["leaves"])


def _leave_out(leave) -> LeaveOut:
    return LeaveOut.model_validate(leave)


def _domain_error(exc: LeaveError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/balance", response_model=list[LeaveBalanceOut])
async def balance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> list[dict]:
    year = year or now_local().year
    return await leave_service.get_balances(db, current_user.id, year)


@router.get("/mine", response_model=PaginatedResponse[LeaveOut])
async def mine(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await leave_service.list_mine(db, current_user.id, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/pending", response_model=PaginatedResponse[LeaveUserRow])
async def pending(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await leave_service.pending_queue(db, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/team-availability", response_model=list[TeamAvailabilityRow])
async def team_availability(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date,
    to_date: date,
) -> list[dict]:
    if to_date < from_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date range")
    return await leave_service.team_availability(db, from_date, to_date)


@router.post("", response_model=LeaveOut, status_code=status.HTTP_201_CREATED)
async def apply(
    payload: LeaveApplyRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeaveOut:
    try:
        leave = await leave_service.apply_leave(db, current_user, payload)
    except LeaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "create", "leave", entity_id=str(leave.id))
    await db.commit()
    return _leave_out(leave)


@router.patch("/{leave_id}", response_model=LeaveOut)
async def cancel(
    leave_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeaveOut:
    try:
        leave = await leave_service.cancel_leave(db, current_user, leave_id)
    except LeaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "cancel", "leave", entity_id=str(leave_id))
    await db.commit()
    return _leave_out(leave)


@router.post("/{leave_id}/approve", response_model=LeaveOut)
async def approve(
    leave_id: int,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeaveOut:
    try:
        leave = await leave_service.approve_leave(db, current_user, leave_id)
    except LeaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await _notify_leave(db, leave, "approved")
    target_user = await db.get(User, leave.user_id)
    if target_user and target_user.email:
        await send_leave_status_email(
            target_user.email,
            target_user.name,
            leave.leave_type.value,
            leave.from_date.isoformat(),
            leave.to_date.isoformat(),
            "approved",
        )
    await log_audit(db, current_user, "approve", "leave", entity_id=str(leave_id))
    await db.commit()
    return _leave_out(leave)


@router.post("/{leave_id}/reject", response_model=LeaveOut)
async def reject(
    leave_id: int,
    payload: LeaveRejectRequest,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LeaveOut:
    try:
        leave = await leave_service.reject_leave(db, current_user, leave_id, payload.reason)
    except LeaveError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await _notify_leave(db, leave, "rejected")
    target_user = await db.get(User, leave.user_id)
    if target_user and target_user.email:
        await send_leave_status_email(
            target_user.email,
            target_user.name,
            leave.leave_type.value,
            leave.from_date.isoformat(),
            leave.to_date.isoformat(),
            "rejected",
            payload.reason,
        )
    await log_audit(db, current_user, "reject", "leave", entity_id=str(leave_id))
    await db.commit()
    return _leave_out(leave)


async def _notify_leave(db: AsyncSession, leave, decision: str) -> None:
    await notify(
        db,
        leave.user_id,
        f"Leave {decision}",
        f"Your {leave.leave_type.value} leave for {leave.from_date.isoformat()} was {decision}.",
        "leave",
        "/leaves/mine",
    )
    await db.commit()
