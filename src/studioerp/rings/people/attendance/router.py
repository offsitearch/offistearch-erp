"""Attendance tracking routes (r2/people). Ported from ``app/modules/attendance/routes.py``.

Endpoints: /attendance — clock-in/out, daily records, per-user summaries,
bulk marking and JSON report. Deferred to owning modules/phases: the holidays
module serves /holidays, and XLSX/CSV report export awaits the reporting phase.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import AttendanceError
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.users import User
from studioerp.rings.people.attendance import service as attendance_service
from studioerp.rings.people.attendance.schemas import (
    AttendanceRecordOut,
    AttendanceUpdateRequest,
    AttendanceUserRow,
    BulkEntryRequest,
    CheckInRequest,
    CheckOutRequest,
    MonthlySummaryOut,
    ReportOut,
    ReportRow,
)
from studioerp.rings.people.identity.repository import user_repository
from studioerp.rings.people.identity.schemas import UserOut
from studioerp.enums import AttendanceStatus
from studioerp.schemas import MessageResponse

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _record_out(record) -> AttendanceRecordOut:
    return AttendanceRecordOut.model_validate(record)


async def _summary(db: AsyncSession, user: User, year: int, month: int) -> MonthlySummaryOut:
    records, totals = await attendance_service.monthly_records(db, user.id, year, month)
    return MonthlySummaryOut(
        user=UserOut.model_validate(user),
        records=[_record_out(record) for record in records],
        totals=totals,
    )


@router.post("/check-in", response_model=AttendanceRecordOut, status_code=status.HTTP_201_CREATED)
async def check_in(
    payload: CheckInRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttendanceRecordOut:
    try:
        record = await attendance_service.check_in(db, current_user, payload)
    except AttendanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "check_in", "attendance", entity_id=str(record.id))
    await db.commit()
    return _record_out(record)


@router.post("/check-out", response_model=AttendanceRecordOut)
async def check_out(
    payload: CheckOutRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttendanceRecordOut:
    try:
        record = await attendance_service.check_out(db, current_user, payload)
    except AttendanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "check_out", "attendance", entity_id=str(record.id))
    await db.commit()
    return _record_out(record)


@router.get("/me", response_model=MonthlySummaryOut)
async def my_attendance(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> MonthlySummaryOut:
    ref = attendance_service.now_local()
    month = month or ref.month
    year = year or ref.year
    return await _summary(db, current_user, year, month)


@router.get("/today", response_model=list[AttendanceUserRow])
async def today(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: int | None = None,
    status_code_: AttendanceStatus | None = Query(default=None, alias="status"),
) -> list[dict]:
    return await attendance_service.rows_for_date(
        db,
        attendance_service.now_local().date(),
        department_id,
        status_code_.value if status_code_ else None,
    )


@router.get("/date/{date}", response_model=list[AttendanceUserRow])
async def by_date(
    date: date,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    department_id: int | None = None,
    status_code_: AttendanceStatus | None = Query(default=None, alias="status"),
) -> list[dict]:
    return await attendance_service.rows_for_date(
        db, date, department_id, status_code_.value if status_code_ else None
    )


@router.get("/employee/{user_id}", response_model=MonthlySummaryOut)
async def employee_attendance(
    user_id: int,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None, ge=2000, le=2100),
) -> MonthlySummaryOut:
    target = await user_repository.get(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    ref = attendance_service.now_local()
    month = month or ref.month
    year = year or ref.year
    records, totals = await attendance_service.monthly_records(db, target.id, year, month)
    return MonthlySummaryOut(
        user=UserOut.model_validate(target),
        records=[_record_out(record) for record in records],
        totals=totals,
    )


@router.post("/bulk", response_model=MessageResponse)
async def bulk(
    payload: BulkEntryRequest,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await attendance_service.bulk_mark(db, current_user, payload.date, payload.entries)
    await log_audit(db, current_user, "bulk_mark", "attendance")
    await db.commit()
    return MessageResponse(
        message=f"Marked attendance for {len({e.user_id for e in payload.entries})} employee(s) on {payload.date}"
    )


@router.patch("/{record_id}", response_model=AttendanceRecordOut)
async def patch_record(
    record_id: int,
    payload: AttendanceUpdateRequest,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttendanceRecordOut:
    try:
        record = await attendance_service.update_record(db, record_id, payload)
    except AttendanceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "update", "attendance", entity_id=str(record_id))
    await db.commit()
    return _record_out(record)


@router.get("/report", response_model=ReportOut)
async def report(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_date: date,
    to_date: date,
    department_id: int | None = None,
) -> ReportOut:
    rows = await attendance_service.report_rows(db, from_date, to_date, department_id)
    return ReportOut(
        from_date=from_date,
        to_date=to_date,
        rows=[ReportRow(**row) for row in rows],
    )
