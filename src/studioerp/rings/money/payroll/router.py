"""Payroll routes: /payroll month view + run lifecycle (ring r4/money).

Payroll is financial data — executive band only (L0/L1) via
``require_financial_access``. Ported from ``app/modules/payroll/routes.py``.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import PayrollError
from studioerp.platform.deps import require_financial_access
from studioerp.platform.users import User
from studioerp.rings.money.payroll import service as payroll_service
from studioerp.rings.money.payroll.schemas import (
    AddEntriesIn,
    MarkPaidIn,
    PayrollAdjustmentIn,
    PayrollEntryUpdate,
    PayrollMonthOut,
    PayrollRunOut,
    RunCreateIn,
)
from studioerp.time import now_local

payroll_router = APIRouter(prefix="/payroll", tags=["payroll"])

CurrentUser = Annotated[User, Depends(require_financial_access())]
DB = Annotated[AsyncSession, Depends(get_db)]


def _domain_error(exc: PayrollError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _run_or_404(db: AsyncSession, run_id: int):
    try:
        return await payroll_service.get_run_or_404(db, run_id)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.get("", response_model=PayrollMonthOut)
async def get_payroll(
    current_user: CurrentUser,
    db: DB,
    month: int = Query(default_factory=lambda: now_local().date().month, ge=1, le=12),
    year: int = Query(default_factory=lambda: now_local().date().year, ge=2020, le=2100),
) -> dict:
    return await payroll_service.get_month(db, month, year)


@payroll_router.post("/runs", response_model=PayrollRunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreateIn,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    try:
        run = await payroll_service.create_run(
            db, payload.month, payload.year, payload.title, current_user
        )
        result = await payroll_service.run_out(db, run)
    except PayrollError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "create", "payroll_run", entity_id=str(result["id"]))
    await db.commit()
    return result


@payroll_router.get("/runs/{run_id}", response_model=PayrollRunOut)
async def get_run(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    return await payroll_service.run_out(db, run)


@payroll_router.post("/runs/{run_id}/entries", response_model=PayrollRunOut)
async def add_entries(
    run_id: int,
    payload: AddEntriesIn,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.add_entries(db, run, payload.user_ids, current_user)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.delete("/runs/{run_id}/entries/{user_id}", response_model=PayrollRunOut)
async def remove_entry(
    run_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.remove_entry(db, run, user_id)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.put("/runs/{run_id}/entries/{user_id}", response_model=PayrollRunOut)
async def update_entry(
    run_id: int,
    user_id: int,
    payload: PayrollEntryUpdate,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        data = payload.model_dump(exclude_unset=True)
        return await payroll_service.update_entry(db, run, user_id, data)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post(
    "/runs/{run_id}/entries/{user_id}/adjustments", response_model=PayrollRunOut
)
async def add_adjustment(
    run_id: int,
    user_id: int,
    payload: PayrollAdjustmentIn,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.add_adjustment(
            db, run, user_id, payload.kind, payload.category, payload.label, payload.amount, current_user
        )
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.delete("/runs/{run_id}/adjustments/{adjustment_id}", response_model=PayrollRunOut)
async def remove_adjustment(
    run_id: int,
    adjustment_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.remove_adjustment(db, run, adjustment_id)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/submit-review", response_model=PayrollRunOut)
async def submit_review(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.submit_review(db, run)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/entries/{user_id}/approve", response_model=PayrollRunOut)
async def approve_entry(
    run_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.approve_entry(db, run, user_id, current_user)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/reopen", response_model=PayrollRunOut)
async def reopen_run(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.reopen_run(db, run)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/process", response_model=PayrollRunOut)
async def process_run(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.process_run(db, run, current_user)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/mark-paid", response_model=PayrollRunOut)
async def mark_paid(
    run_id: int,
    payload: MarkPaidIn,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.mark_paid(
            db, run, current_user, payload.payment_method, payload.payment_reference
        )
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.post("/runs/{run_id}/cancel", response_model=PayrollRunOut)
async def cancel_run(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> dict:
    run = await _run_or_404(db, run_id)
    try:
        return await payroll_service.cancel_run(db, run)
    except PayrollError as exc:
        raise _domain_error(exc) from exc


@payroll_router.delete("/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: int,
    current_user: CurrentUser,
    db: DB,
) -> Response:
    run = await _run_or_404(db, run_id)
    try:
        await payroll_service.delete_run(db, run)
    except PayrollError as exc:
        raise _domain_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@payroll_router.get("/runs/{run_id}/payslips/{user_id}")
async def download_payslip(
    run_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: DB,
) -> Response:
    run = await _run_or_404(db, run_id)
    try:
        content, filename = await payroll_service.get_payslip(db, run, user_id)
    except PayrollError as exc:
        raise _domain_error(exc) from exc
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
