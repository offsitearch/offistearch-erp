"""Payroll service (ring r4/money). Ported from ``app/modules/payroll/service.py``.

Monthly payroll runs, per-employee build/review/process/paid, proration control,
audited bonus/deduction adjustments, and payslip PDFs.
"""

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.enums import (
    AttendanceStatus,
    PayrollAdjustmentCategory,
    PayrollAdjustmentKind,
    PayrollEntryStatus,
    PayrollStatus,
)
from studioerp.errors import PayrollError
from studioerp.money import q as _q
from studioerp.pdf import payslip_pdf
from studioerp.platform.orgstructure.models import Department
from studioerp.platform.users import User
from studioerp.rings.money.payroll.models import (
    PayrollAdjustment,
    PayrollEntry,
    PayrollRun,
    SalaryComponent,
)
from studioerp.rings.people.attendance.models import Attendance
from studioerp.rings.people.holidays.models import Holiday
from studioerp.time import utc_now

_WORK_DAY_STATUSES = (
    AttendanceStatus.PRESENT,
    AttendanceStatus.LATE,
    AttendanceStatus.HALF_DAY,
    AttendanceStatus.WORK_FROM_HOME,
    AttendanceStatus.ON_LEAVE,
)

_ZERO = Decimal("0")


# ── basic helpers ─────────────────────────────────────────────────────────────
def _month_weekdays(month: int, year: int) -> int:
    last_day = calendar.monthrange(year, month)[1]
    return sum(1 for day in range(1, last_day + 1) if date(year, month, day).weekday() < 5)


async def _holidays(db: AsyncSession, month: int, year: int) -> set[date]:
    start = date(year, month, 1)
    end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
    rows = await db.execute(select(Holiday.date).where(Holiday.date >= start, Holiday.date < end))
    return set(rows.scalars().all())


def _payable_days(month: int, year: int, holidays: set[date]) -> int:
    """Working days payable: weekday count minus public holidays on weekdays."""
    return _month_weekdays(month, year) - sum(1 for h in holidays if h.weekday() < 5)


def _enum_value(v) -> str:
    return v.value if hasattr(v, "value") else v


def _fmt_date(d) -> str:
    if d is None:
        return "-----"
    if hasattr(d, "strftime"):
        return d.strftime("%d %b %Y")
    return str(d)


def _components(
    salary: SalaryComponent | None,
    working_days: int,
    payable: int,
    prorate: bool,
    zero: bool = False,
) -> dict[str, Decimal]:
    """Prorated (or full, when ``prorate`` is off) monthly earnings breakdown."""
    if salary is None or zero:
        basic = hra = special = pf = _ZERO
    else:
        ratio = (Decimal(working_days or 0) / Decimal(payable)) if payable else Decimal("0")
        if not prorate:
            ratio = Decimal("1")
        basic = _q(Decimal(salary.basic or 0) * ratio)
        hra = _q(Decimal(salary.hra or 0) * ratio)
        special = _q(Decimal(salary.special_allowance or 0) * ratio)
        pf = _q(Decimal(salary.pf_deduction or 0) * ratio)
    base_gross = _q(basic + hra + special)
    return {"basic": basic, "hra": hra, "special": special, "pf": pf, "base_gross": base_gross}


async def _working_days_map(
    db: AsyncSession, user_ids: list[int], month: int, year: int, holidays: set[date]
) -> dict[int, int]:
    if not user_ids:
        return {}
    start = date(year, month, 1)
    end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
    rows = (
        await db.execute(
            select(Attendance.user_id, Attendance.date).where(
                Attendance.user_id.in_(user_ids),
                Attendance.date >= start,
                Attendance.date < end,
                Attendance.status.in_(_WORK_DAY_STATUSES),
            )
        )
    ).all()
    user_dates: dict[int, set[date]] = {}
    for uid, dt in rows:
        user_dates.setdefault(uid, set()).add(dt)
    return {uid: sum(1 for d in dates if d not in holidays) for uid, dates in user_dates.items()}


async def _user_salary_rows(
    db: AsyncSession, user_ids: list[int] | None = None, active_only: bool = True
) -> list[tuple[User, SalaryComponent | None, str | None]]:
    stmt = (
        select(User, SalaryComponent, Department.name)
        .outerjoin(SalaryComponent, SalaryComponent.user_id == User.id)
        .outerjoin(Department, Department.id == User.department_id)
        .order_by(User.name)
    )
    if active_only:
        stmt = stmt.where(User.is_active.is_(True))
    if user_ids is not None:
        stmt = stmt.where(User.id.in_(user_ids))
    return (await db.execute(stmt)).all()


async def _paid_this_month(
    db: AsyncSession,
    user_ids: list[int],
    month: int,
    year: int,
    before_run_id: int | None = None,
) -> set[int]:
    """Users who already hold an entry in a processed/paid run this month."""
    if not user_ids:
        return set()
    stmt = (
        select(PayrollEntry.user_id)
        .join(PayrollRun, PayrollRun.id == PayrollEntry.payroll_run_id)
        .where(
            PayrollRun.month == month,
            PayrollRun.year == year,
            PayrollRun.status.in_([PayrollStatus.PROCESSED, PayrollStatus.PAID]),
            PayrollEntry.user_id.in_(user_ids),
        )
    )
    if before_run_id is not None:
        stmt = stmt.where(PayrollRun.id < before_run_id)
    return set((await db.execute(stmt)).scalars().all())


async def _adjustments_for(
    db: AsyncSession, entry_ids: list[int]
) -> dict[int, list[PayrollAdjustment]]:
    if not entry_ids:
        return {}
    rows = (
        (
            await db.execute(
                select(PayrollAdjustment)
                .where(PayrollAdjustment.payroll_entry_id.in_(entry_ids))
                .order_by(PayrollAdjustment.id)
            )
        )
        .scalars()
        .all()
    )
    grouped: dict[int, list[PayrollAdjustment]] = {}
    for adj in rows:
        grouped.setdefault(adj.payroll_entry_id, []).append(adj)
    return grouped


def _adj_out(adj: PayrollAdjustment) -> dict:
    return {
        "id": adj.id,
        "kind": _enum_value(adj.kind),
        "category": _enum_value(adj.category),
        "label": adj.label,
        "amount": adj.amount,
        "created_by": adj.created_by,
        "created_at": adj.created_at,
    }


def _adjustment_totals(adjustments: list[PayrollAdjustment]) -> tuple[Decimal, Decimal]:
    additions = sum(
        (a.amount for a in adjustments if a.kind == PayrollAdjustmentKind.ADDITION), _ZERO
    )
    extra = sum(
        (a.amount for a in adjustments if a.kind == PayrollAdjustmentKind.DEDUCTION), _ZERO
    )
    return additions, extra


def _entry_out(
    entry: PayrollEntry,
    user: User,
    department_name: str | None,
    adjustments: list[PayrollAdjustment],
    already_paid: bool = False,
) -> dict:
    additions, extra = _adjustment_totals(adjustments)
    return {
        "user_id": user.id,
        "user_name": user.name,
        "employee_id": user.employee_id,
        "designation": user.designation,
        "department": department_name,
        "date_of_joining": user.date_of_joining,
        "already_paid": already_paid,
        "working_days": entry.working_days,
        "total_days": entry.total_days,
        "prorate": entry.prorate,
        "basic_amount": entry.basic_amount,
        "hra_amount": entry.hra_amount,
        "special_amount": entry.special_amount,
        "base_gross": entry.base_gross,
        "pf_deduction": entry.pf_deduction,
        "gross_salary": entry.gross_salary,
        "deductions": entry.deductions,
        "net_pay": entry.net_pay,
        "additions_total": additions,
        "deductions_extra_total": extra,
        "adjustments": [_adj_out(a) for a in adjustments],
        "entry_status": _enum_value(entry.entry_status),
        "notes": entry.notes,
        "approved_by": entry.approved_by,
        "approved_at": entry.approved_at,
        "payment_ref": entry.payment_ref,
        "paid_at": entry.paid_at,
    }


async def run_out(db: AsyncSession, run: PayrollRun) -> dict:
    rows = (
        await db.execute(
            select(PayrollEntry, User, Department.name)
            .join(User, User.id == PayrollEntry.user_id)
            .outerjoin(Department, Department.id == User.department_id)
            .where(PayrollEntry.payroll_run_id == run.id)
            .order_by(User.name)
        )
    ).all()
    entry_ids = [entry.id for entry, _, _ in rows]
    adjustments = await _adjustments_for(db, entry_ids)
    already_paid = await _paid_this_month(
        db, [user.id for _, user, _ in rows], run.month, run.year, before_run_id=run.id
    )
    entries = [
        _entry_out(entry, user, dept, adjustments.get(entry.id, []), entry.user_id in already_paid)
        for entry, user, dept in rows
    ]
    return {
        "id": run.id,
        "title": run.title,
        "month": run.month,
        "year": run.year,
        "status": _enum_value(run.status),
        "created_by": run.created_by,
        "created_at": run.created_at,
        "processed_by": run.processed_by,
        "processed_at": run.processed_at,
        "paid_at": run.paid_at,
        "payment_method": run.payment_method,
        "payment_reference": run.payment_reference,
        "entries": entries,
        "total_gross": _q(sum((e["gross_salary"] for e in entries), _ZERO)),
        "total_deductions": _q(sum((e["deductions"] for e in entries), _ZERO)),
        "total_net": _q(sum((e["net_pay"] for e in entries), _ZERO)),
        "total_working_days": sum((e["working_days"] for e in entries), 0),
        "headcount": len(entries),
        "approved_count": sum(1 for e in entries if e["entry_status"] == "approved"),
    }


# ── read / month view ─────────────────────────────────────────────────────────
async def compute_entries(db: AsyncSession, month: int, year: int) -> list[dict]:
    """Computed preview figures for every active salaried employee."""
    holidays = await _holidays(db, month, year)
    payable = _payable_days(month, year, holidays)
    rows = await _user_salary_rows(db, active_only=True)
    rows = [(u, s, d) for u, s, d in rows if s is not None]
    wd_map = await _working_days_map(
        db, [user.id for user, _, _ in rows], month, year, holidays
    )
    already_paid = await _paid_this_month(db, [user.id for user, _, _ in rows], month, year)
    entries: list[dict] = []
    for user, salary, dept in rows:
        working_days = wd_map.get(user.id, 0)
        comp = _components(
            salary, working_days, payable, prorate=True, zero=user.id in already_paid
        )
        gross = comp["base_gross"]
        entries.append(
            {
                "user_id": user.id,
                "user_name": user.name,
                "employee_id": user.employee_id,
                "designation": user.designation,
                "department": dept,
                "date_of_joining": user.date_of_joining,
                "working_days": working_days,
                "total_days": payable,
                "prorate": True,
                "already_paid": user.id in already_paid,
                "basic_amount": comp["basic"],
                "hra_amount": comp["hra"],
                "special_amount": comp["special"],
                "base_gross": comp["base_gross"],
                "pf_deduction": comp["pf"],
                "gross_salary": gross,
                "deductions": comp["pf"],
                "net_pay": _q(gross - comp["pf"]),
                "additions_total": _ZERO,
                "deductions_extra_total": _ZERO,
                "adjustments": [],
                "entry_status": "included",
                "notes": None,
                "approved_by": None,
                "approved_at": None,
                "payment_ref": None,
                "paid_at": None,
            }
        )
    return entries


async def get_month(db: AsyncSession, month: int, year: int) -> dict:
    runs = (
        (await db.execute(
            select(PayrollRun)
            .where(PayrollRun.month == month, PayrollRun.year == year)
            .order_by(PayrollRun.id)
        ))
        .scalars()
        .all()
    )
    runs_out = [await run_out(db, run) for run in runs]
    preview = await compute_entries(db, month, year)
    return {
        "month": month,
        "year": year,
        "runs": runs_out,
        "preview": preview,
        "preview_total_net": _q(sum((e["net_pay"] for e in preview), _ZERO)),
    }


# ── run / entry lifecycle ─────────────────────────────────────────────────────
async def get_run_or_404(db: AsyncSession, run_id: int) -> PayrollRun:
    run = (
        await db.execute(select(PayrollRun).where(PayrollRun.id == run_id))
    ).scalar_one_or_none()
    if run is None:
        raise PayrollError("Payroll run not found", 404)
    return run


def _assert_status(run: PayrollRun, expected: PayrollStatus, message: str) -> None:
    if run.status != expected:
        raise PayrollError(message, 409)


def _find_entry(run: PayrollRun, user_id: int) -> PayrollEntry | None:
    return next((e for e in run.entries if e.user_id == user_id), None)


async def create_run(
    db: AsyncSession, month: int, year: int, title: str, actor: User
) -> PayrollRun:
    run = PayrollRun(
        month=month,
        year=year,
        title=title.strip() if title else "",
        status=PayrollStatus.DRAFT,
        created_by=actor.id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def add_entries(
    db: AsyncSession, run: PayrollRun, user_ids: list[int], actor: User
) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Employees can only be added while the run is a draft")
    existing = {e.user_id for e in run.entries}
    wanted = [uid for uid in dict.fromkeys(user_ids) if uid is not None and uid not in existing]
    if not wanted:
        return await run_out(db, run)
    rows = await _user_salary_rows(db, user_ids=wanted, active_only=True)
    holidays = await _holidays(db, run.month, run.year)
    payable = _payable_days(run.month, run.year, holidays)
    wd_map = await _working_days_map(db, [user.id for user, _, _ in rows], run.month, run.year, holidays)
    already_paid = await _paid_this_month(
        db, [user.id for user, _, _ in rows], run.month, run.year, before_run_id=run.id
    )
    for user, salary, _dept in rows:
        working_days = wd_map.get(user.id, 0)
        comp = _components(
            salary, working_days, payable, prorate=True, zero=user.id in already_paid
        )
        db.add(
            PayrollEntry(
                payroll_run_id=run.id,
                user_id=user.id,
                working_days=working_days,
                total_days=payable,
                prorate=True,
                basic_amount=comp["basic"],
                hra_amount=comp["hra"],
                special_amount=comp["special"],
                pf_deduction=comp["pf"],
                base_gross=comp["base_gross"],
                gross_salary=comp["base_gross"],
                deductions=comp["pf"],
                net_pay=_q(comp["base_gross"] - comp["pf"]),
                entry_status=PayrollEntryStatus.INCLUDED,
            )
        )
    await db.commit()
    return await run_out(db, run)


async def remove_entry(db: AsyncSession, run: PayrollRun, user_id: int) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Employees can only be removed while the run is a draft")
    entry = _find_entry(run, user_id)
    if entry is None:
        raise PayrollError("Employee is not part of this payroll run", 404)
    await db.execute(delete(PayrollAdjustment).where(PayrollAdjustment.payroll_entry_id == entry.id))
    await db.execute(delete(PayrollEntry).where(PayrollEntry.id == entry.id))
    await db.commit()
    return await run_out(db, run)


async def update_entry(
    db: AsyncSession, run: PayrollRun, user_id: int, data: dict
) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Entries are locked once the run leaves draft")
    entry = _find_entry(run, user_id)
    if entry is None:
        raise PayrollError("Employee is not part of this payroll run", 404)
    salary = await db.scalar(select(SalaryComponent).where(SalaryComponent.user_id == user_id))
    working_days = entry.working_days
    if data.get("working_days") is not None:
        working_days = data["working_days"]
    prorate = data["prorate"] if data.get("prorate") is not None else entry.prorate
    if "notes" in data:
        entry.notes = data["notes"] or None
    holidays = await _holidays(db, run.month, run.year)
    payable = _payable_days(run.month, run.year, holidays)
    already_paid = await _paid_this_month(
        db, [user_id], run.month, run.year, before_run_id=run.id
    )
    comp = _components(
        salary, working_days, payable, prorate, zero=user_id in already_paid
    )
    entry.working_days = working_days
    entry.total_days = payable
    entry.prorate = prorate
    entry.basic_amount = comp["basic"]
    entry.hra_amount = comp["hra"]
    entry.special_amount = comp["special"]
    entry.pf_deduction = comp["pf"]
    entry.base_gross = comp["base_gross"]
    adjustments = (await _adjustments_for(db, [entry.id])).get(entry.id, [])
    _apply_totals(entry, adjustments)
    _ensure_net_not_negative(entry)
    await db.commit()
    return await run_out(db, run)


def _apply_totals(entry: PayrollEntry, adjustments: list[PayrollAdjustment]) -> None:
    additions, extra = _adjustment_totals(adjustments)
    gross = _q(entry.base_gross + additions)
    deductions = _q(entry.pf_deduction + extra)
    entry.gross_salary = gross
    entry.deductions = deductions
    entry.net_pay = _q(gross - deductions)


def _ensure_net_not_negative(entry: PayrollEntry) -> None:
    if entry.net_pay < 0:
        raise PayrollError(
            f"Adjustments make net pay negative for employee #{entry.user_id}", 409
        )


async def add_adjustment(
    db: AsyncSession,
    run: PayrollRun,
    user_id: int,
    kind: str,
    category: str,
    label: str,
    amount: Decimal,
    actor: User,
) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Adjustments can only be made while the run is a draft")
    entry = _find_entry(run, user_id)
    if entry is None:
        raise PayrollError("Employee is not part of this payroll run", 404)
    existing = (await _adjustments_for(db, [entry.id])).get(entry.id, [])
    adjustment = PayrollAdjustment(
        payroll_entry_id=entry.id,
        kind=PayrollAdjustmentKind(kind),
        category=PayrollAdjustmentCategory(category),
        label=label.strip(),
        amount=_q(amount),
        created_by=actor.id,
    )
    _apply_totals(entry, existing + [adjustment])
    _ensure_net_not_negative(entry)
    db.add(adjustment)
    await db.commit()
    return await run_out(db, run)


async def remove_adjustment(db: AsyncSession, run: PayrollRun, adjustment_id: int) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Adjustments can only be removed while the run is a draft")
    adjustment = await db.get(PayrollAdjustment, adjustment_id)
    if adjustment is None:
        raise PayrollError("Adjustment not found", 404)
    entry = next((e for e in run.entries if e.id == adjustment.payroll_entry_id), None)
    if entry is None:
        raise PayrollError("Adjustment does not belong to this run", 404)
    remaining = [
        a
        for a in (await _adjustments_for(db, [entry.id])).get(entry.id, [])
        if a.id != adjustment_id
    ]
    await db.execute(delete(PayrollAdjustment).where(PayrollAdjustment.id == adjustment_id))
    _apply_totals(entry, remaining)
    _ensure_net_not_negative(entry)
    await db.commit()
    return await run_out(db, run)


async def submit_review(db: AsyncSession, run: PayrollRun) -> dict:
    _assert_status(run, PayrollStatus.DRAFT, "Only a draft run can be submitted for review")
    if not run.entries:
        raise PayrollError("Add at least one employee before submitting for review", 409)
    run.status = PayrollStatus.REVIEW
    await db.commit()
    return await run_out(db, run)


async def approve_entry(db: AsyncSession, run: PayrollRun, user_id: int, actor: User) -> dict:
    _assert_status(run, PayrollStatus.REVIEW, "Only a run under review can be approved")
    entry = _find_entry(run, user_id)
    if entry is None:
        raise PayrollError("Employee is not part of this payroll run", 404)
    entry.entry_status = PayrollEntryStatus.APPROVED
    entry.approved_by = actor.id
    entry.approved_at = utc_now()
    await db.commit()
    return await run_out(db, run)


async def reopen_run(db: AsyncSession, run: PayrollRun) -> dict:
    if run.status not in (PayrollStatus.DRAFT, PayrollStatus.REVIEW):
        raise PayrollError("Only draft or review runs can be reopened", 409)
    run.status = PayrollStatus.DRAFT
    for entry in run.entries:
        entry.entry_status = PayrollEntryStatus.INCLUDED
        entry.approved_by = None
        entry.approved_at = None
    await db.commit()
    return await run_out(db, run)


async def process_run(db: AsyncSession, run: PayrollRun, actor: User) -> dict:
    _assert_status(run, PayrollStatus.REVIEW, "Submit the run for review and approve every employee first")
    if not run.entries:
        raise PayrollError("No employees in this run", 409)
    pending = [e for e in run.entries if e.entry_status != PayrollEntryStatus.APPROVED]
    if pending:
        pending_ids = [e.user_id for e in pending]
        names = dict(
            (await db.execute(select(User.id, User.name).where(User.id.in_(pending_ids)))).all()
        )
        raised = ", ".join(names.get(uid, f"#{uid}") for uid in pending_ids)
        raise PayrollError(
            f"Cannot process: {len(pending)} employee(s) not approved yet — {raised}", 409
        )

    salaried = {e.user_id for e in run.entries if e.base_gross > _ZERO}
    double_paid: list[int] = []
    if salaried:
        double_paid = (
            await db.execute(
                select(PayrollEntry.user_id)
                .join(PayrollRun, PayrollRun.id == PayrollEntry.payroll_run_id)
                .where(
                    PayrollRun.month == run.month,
                    PayrollRun.year == run.year,
                    PayrollRun.id != run.id,
                    PayrollRun.status.in_([PayrollStatus.PROCESSED, PayrollStatus.PAID]),
                    PayrollEntry.user_id.in_(salaried),
                )
            )
        ).scalars().all()
    if double_paid:
        raise PayrollError(
            "Employees already paid in another processed run for this month: "
            + ", ".join(str(uid) for uid in sorted(double_paid)),
            409,
        )

    run.status = PayrollStatus.PROCESSED
    run.processed_by = actor.id
    run.processed_at = utc_now()
    for entry in run.entries:
        entry.payslip_path = f"payroll/{run.id}/{entry.user_id}.pdf"
    await db.commit()
    return await run_out(db, run)


async def mark_paid(
    db: AsyncSession, run: PayrollRun, actor: User, payment_method: str | None, payment_reference: str | None
) -> dict:
    _assert_status(run, PayrollStatus.PROCESSED, "Only a processed run can be marked as paid")
    run.status = PayrollStatus.PAID
    run.paid_at = utc_now()
    run.payment_method = payment_method or None
    run.payment_reference = payment_reference or None
    for entry in run.entries:
        entry.entry_status = PayrollEntryStatus.PAID
        entry.paid_by = actor.id
        entry.paid_at = run.paid_at
        entry.payment_ref = run.payment_reference
    await db.commit()
    return await run_out(db, run)


async def cancel_run(db: AsyncSession, run: PayrollRun) -> dict:
    if run.status not in (PayrollStatus.DRAFT, PayrollStatus.REVIEW):
        raise PayrollError("Only draft or review runs can be cancelled", 409)
    run.status = PayrollStatus.CANCELLED
    await db.commit()
    return await run_out(db, run)


async def delete_run(db: AsyncSession, run: PayrollRun) -> None:
    _assert_status(run, PayrollStatus.DRAFT, "Only a draft run can be deleted")
    entry_ids = [e.id for e in run.entries]
    if entry_ids:
        await db.execute(
            delete(PayrollAdjustment).where(PayrollAdjustment.payroll_entry_id.in_(entry_ids))
        )
    await db.execute(delete(PayrollEntry).where(PayrollEntry.payroll_run_id == run.id))
    await db.execute(delete(PayrollRun).where(PayrollRun.id == run.id))
    await db.commit()


# ── payslips ──────────────────────────────────────────────────────────────────
async def get_payslip(db: AsyncSession, run: PayrollRun, user_id: int) -> tuple[bytes, str]:
    if run.status == PayrollStatus.DRAFT:
        raise PayrollError("Payslips are only available after the run is processed", 409)
    entry = _find_entry(run, user_id)
    if entry is None:
        raise PayrollError("Payslip not found for this employee", 404)
    user = await db.get(User, user_id)
    name = user.name if user else f"User #{user_id}"
    employee_id = (user.employee_id if user and user.employee_id else None) or f"U-{user_id}"
    designation = user.designation if user else None
    month_label = f"{calendar.month_name[run.month]} {run.year}"
    content = payslip_pdf(
        employee_name=name,
        employee_id=employee_id,
        designation=designation or "",
        month_label=month_label,
        working_days=entry.working_days,
        gross_salary=entry.gross_salary,
        deductions=entry.deductions,
        net_pay=entry.net_pay,
    )
    filename = f"payslip-{user_id}-{run.month}-{run.year}.pdf"
    return content, filename
