"""Finance routes: /finance summary, /invoices, /expenses (ring r4/money).

All financial data is restricted to the executive band (L0 CEO / L1 Director)
via ``require_financial_access``. My-expenses are open to any staff member for
their own reimbursement claims.

Deferred (storage/PDF/email abstractions pending): invoice PDF download, receipt
upload/download, and the send-invoice email.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import FinanceError
from studioerp.platform.deps import get_current_user, require_financial_access
from studioerp.platform.users import User
from studioerp.rings.money.finance import service as finance_service
from studioerp.rings.money.finance.models import Expense, Invoice
from studioerp.rings.money.finance.schemas import (
    ExpenseCreate,
    ExpenseDecisionIn,
    ExpenseOut,
    InvoiceCreate,
    InvoiceOut,
    InvoicePaymentIn,
    InvoiceUpdate,
)
from studioerp.schemas import PaginatedResponse

finance_router = APIRouter(prefix="/finance", tags=["finance"])
invoices_router = APIRouter(prefix="/invoices", tags=["invoices"])
expenses_router = APIRouter(prefix="/expenses", tags=["expenses"])


def _domain_error(exc: FinanceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _get_or_404(db: AsyncSession, model, object_id: int):
    obj = await db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return obj


# ── /finance ──────────────────────────────────────────────────────────────

@finance_router.get("/overview")
async def finance_overview(
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
    period: str = Query(default="month", pattern="^(month|quarter|year|all)$"),
    compare: bool = Query(default=False),
) -> dict:
    return await finance_service.finance_overview(db, period, compare=compare)


@finance_router.get("/my-expenses", response_model=PaginatedResponse[ExpenseOut])
async def list_my_expenses(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
    project_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await finance_service.list_expenses(
        db,
        category,
        project_id,
        status_,
        month,
        year,
        paid_by=current_user.name,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@finance_router.post("/my-expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_my_expense(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    payload: ExpenseCreate,
) -> dict:
    payload.paid_by = current_user.name
    return await finance_service.create_expense(db, payload)


# ── /invoices ─────────────────────────────────────────────────────────────

@invoices_router.get("", response_model=PaginatedResponse[InvoiceOut])
async def list_invoices(
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_: str | None = Query(default=None, alias="status"),
    client_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await finance_service.list_invoices(
        db, status_, client_id, search, page, page_size
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@invoices_router.post("", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        result = await finance_service.create_invoice(db, payload)
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "create", "invoice", entity_id=str(result["id"]))
    await db.commit()
    return result


@invoices_router.get("/{invoice_id}", response_model=InvoiceOut)
async def get_invoice(
    invoice_id: int,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        return await finance_service.get_invoice(db, invoice_id)
    except FinanceError as exc:
        raise _domain_error(exc) from exc


@invoices_router.patch("/{invoice_id}", response_model=InvoiceOut)
async def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    invoice = await _get_or_404(db, Invoice, invoice_id)
    try:
        result = await finance_service.update_invoice(db, invoice, payload)
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "update", "invoice", entity_id=str(invoice_id))
    await db.commit()
    return result


@invoices_router.post("/{invoice_id}/send", response_model=InvoiceOut)
async def send_invoice(
    invoice_id: int,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    invoice = await _get_or_404(db, Invoice, invoice_id)
    try:
        result = await finance_service.send_invoice(db, invoice)
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "send", "invoice", entity_id=str(invoice_id))
    await db.commit()
    # Email delivery to the client is deferred until the email module lands.
    return result


@invoices_router.post("/{invoice_id}/payment", response_model=InvoiceOut)
async def record_payment(
    invoice_id: int,
    payload: InvoicePaymentIn,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    invoice = await _get_or_404(db, Invoice, invoice_id)
    try:
        result = await finance_service.record_payment(
            db, invoice, payload.amount, payload.method, payload.payment_date
        )
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "payment", "invoice", entity_id=str(invoice_id))
    await db.commit()
    return result


# ── /expenses ─────────────────────────────────────────────────────────────

@expenses_router.get("", response_model=PaginatedResponse[ExpenseOut])
async def list_expenses(
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None),
    project_id: int | None = Query(default=None),
    status_: str | None = Query(default=None, alias="status"),
    month: int | None = Query(default=None, ge=1, le=12),
    year: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    items, total = await finance_service.list_expenses(
        db, category, project_id, status_, month, year, page=page, page_size=page_size
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@expenses_router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
async def create_expense(
    payload: ExpenseCreate,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        result = await finance_service.create_expense(db, payload)
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "create", "expense", entity_id=str(result["id"]))
    await db.commit()
    return result


@expenses_router.patch("/{expense_id}/approve", response_model=ExpenseOut)
async def decide_expense(
    expense_id: int,
    payload: ExpenseDecisionIn,
    current_user: Annotated[User, Depends(require_financial_access())],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    expense = await _get_or_404(db, Expense, expense_id)
    try:
        result = await finance_service.decide_expense(db, expense, payload.approve, current_user)
    except FinanceError as exc:
        raise _domain_error(exc) from exc
    action = "approve" if payload.approve else "reject"
    await log_audit(db, current_user, action, "expense", entity_id=str(expense_id))
    await db.commit()
    return result
