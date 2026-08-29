"""Timesheet routes (ring r3/work). Ported from ``app/modules/timesheets/routes.py``.

Endpoints: /timesheets — daily entry logging (today only, rejected days
reopen), week/day submit for review, lead+ approval per day or in bulk,
admin listing.

Deferred (reporting phase): month XLSX/PDF export and the per-sheet PDF
receipt.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import TimesheetError
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.users import User
from studioerp.rbac import has_min_level
from studioerp.rings.work.timesheets import service as timesheet_service
from studioerp.rings.work.timesheets.models import Timesheet
from studioerp.rings.work.timesheets.schemas import RejectRequest, TimesheetDetail, TimesheetRow
from studioerp.rings.work.timesheets.schemas import TimesheetWeekSave
from studioerp.schemas import PaginatedResponse
from studioerp.time import now_local

router = APIRouter(prefix="/timesheets", tags=["timesheets"])


def _today() -> date:
    return now_local().date()


def _domain_error(exc: TimesheetError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _authorise_view(db: AsyncSession, timesheet_id: int, user: User) -> None:
    """Owner or L3+ may view a sheet; others get the standard 404."""
    sheet = await db.get(Timesheet, timesheet_id)
    if sheet is None or (sheet.user_id != user.id and not has_min_level(user, "L3")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")


@router.get("/week", response_model=TimesheetDetail)
async def my_week(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    date: date | None = Query(default=None),
) -> dict:
    """The caller's timesheet for the week containing ``date`` (defaults to today).

    Missing weeks are created on demand as drafts.
    """
    try:
        return await timesheet_service.get_week_detail(db, current_user.id, date or _today())
    except TimesheetError as exc:
        raise _domain_error(exc) from exc


@router.put("/week", response_model=TimesheetDetail)
async def save_week(
    payload: TimesheetWeekSave,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.save_week(db, current_user.id, payload)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "update", "timesheet", entity_id=str(detail["id"]))
    await db.commit()
    return detail


@router.get("/mine", response_model=PaginatedResponse[TimesheetRow])
async def mine(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await timesheet_service.list_mine(db, current_user.id, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/pending", response_model=PaginatedResponse[TimesheetRow])
async def pending(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> PaginatedResponse:
    """Submitted sheets awaiting review — strictly junior owners only
    (L0 sees all)."""
    items, total = await timesheet_service.pending_queue(db, current_user, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("", response_model=PaginatedResponse[TimesheetRow])
async def admin_list(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: int | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    from_week: date | None = None,
    to_week: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await timesheet_service.admin_list(
        db, page, page_size, user_id, status_filter, from_week, to_week
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{timesheet_id}", response_model=TimesheetDetail)
async def get_timesheet(
    timesheet_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    await _authorise_view(db, timesheet_id, current_user)
    try:
        return await timesheet_service.get_detail(db, timesheet_id)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc


@router.post("/{timesheet_id}/submit", response_model=TimesheetDetail)
async def submit(
    timesheet_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.submit_timesheet(db, current_user.id, timesheet_id)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "submit", "timesheet", entity_id=str(timesheet_id))
    await db.commit()
    return detail


@router.post("/{timesheet_id}/approve", response_model=TimesheetDetail)
async def approve(
    timesheet_id: int,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.approve_timesheet(db, current_user, timesheet_id)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "approve", "timesheet", entity_id=str(timesheet_id))
    await db.commit()
    return detail


@router.post("/{timesheet_id}/reject", response_model=TimesheetDetail)
async def reject(
    timesheet_id: int,
    payload: RejectRequest,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.reject_timesheet(
            db, current_user, timesheet_id, payload.reason
        )
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "reject", "timesheet", entity_id=str(timesheet_id))
    await db.commit()
    return detail


@router.post("/{timesheet_id}/days/{day}/submit", response_model=TimesheetDetail)
async def submit_day(
    timesheet_id: int,
    day: date,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Owner submits a single day of their own week."""
    try:
        detail = await timesheet_service.submit_day(db, current_user.id, timesheet_id, day)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(
        db,
        current_user,
        "submit_day",
        "timesheet",
        entity_id=str(timesheet_id),
        details={"day": day.isoformat()},
    )
    await db.commit()
    return detail


@router.post("/{timesheet_id}/days/{day}/approve", response_model=TimesheetDetail)
async def approve_day(
    timesheet_id: int,
    day: date,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.approve_day(db, current_user, timesheet_id, day)
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(
        db,
        current_user,
        "approve_day",
        "timesheet",
        entity_id=str(timesheet_id),
        details={"day": day.isoformat()},
    )
    await db.commit()
    return detail


@router.post("/{timesheet_id}/days/{day}/reject", response_model=TimesheetDetail)
async def reject_day(
    timesheet_id: int,
    day: date,
    payload: RejectRequest,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        detail = await timesheet_service.reject_day(
            db, current_user, timesheet_id, day, payload.reason
        )
    except TimesheetError as exc:
        raise _domain_error(exc) from exc
    await log_audit(
        db,
        current_user,
        "reject_day",
        "timesheet",
        entity_id=str(timesheet_id),
        details={"day": day.isoformat(), "reason": payload.reason},
    )
    await db.commit()
    return detail
