"""Ring 4 (money) tests — non-DB: schema validation, pure logic, route assembly."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

# Register the platform Department/OrgLevel mappers before constructing any ORM
# instance below — User.department resolves "Department" by string name and would
# otherwise fail configure_mappers() (normally satisfied by app.py's imports).
import studioerp.platform.orgstructure.models as _org  # noqa: F401
import studioerp.platform.users as _users  # noqa: F401

from studioerp.enums import ClientType, DealStage, ExpenseStatus, InvoiceStatus
from studioerp.rings.money.clients.models import Client
from studioerp.rings.money.clients.service import _client_dict
from studioerp.rings.money.clients.schemas import ClientCreate
from studioerp.rings.money.finance import service as fin
from studioerp.rings.money.finance.models import Expense, Invoice, InvoiceItem
from studioerp.rings.money.finance.schemas import (
    ExpenseCreate,
    InvoiceCreate,
    InvoiceItemIn,
    InvoicePaymentIn,
)


# ── finance schemas ───────────────────────────────────────────────────────

class TestFinanceSchemas:
    def test_currency_defaults_inr(self):
        inv = InvoiceCreate(
            client_id=1,
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 3, 15),
            items=[InvoiceItemIn(description="Design fee", rate=Decimal("1000"))],
        )
        assert inv.currency == "INR"

    def test_currency_accepts_upper(self):
        inv = InvoiceCreate(
            client_id=1,
            invoice_date=date(2026, 3, 1),
            due_date=date(2026, 3, 15),
            currency="usd",
            items=[InvoiceItemIn(description="Design fee", rate=Decimal("50"))],
        )
        assert inv.currency == "USD"

    def test_currency_rejects_unknown(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2026, 3, 1),
                due_date=date(2026, 3, 15),
                currency="XYZ",
                items=[InvoiceItemIn(description="Design fee")],
            )

    def test_invoice_requires_at_least_one_item(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2026, 3, 1),
                due_date=date(2026, 3, 15),
                items=[],
            )

    def test_tax_percent_bounds(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2026, 3, 1),
                due_date=date(2026, 3, 15),
                tax_percent=Decimal("101"),
                items=[InvoiceItemIn(description="Design fee")],
            )

    def test_invoice_item_quantity_non_negative(self):
        with pytest.raises(ValidationError):
            InvoiceItemIn(description="x", quantity=Decimal("-1"))

    def test_expense_amount_must_be_positive(self):
        with pytest.raises(ValidationError):
            ExpenseCreate(category="office", amount=Decimal("0"))

    def test_payment_amount_positive(self):
        with pytest.raises(ValidationError):
            InvoicePaymentIn(amount=Decimal("0"))

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            InvoiceCreate(
                client_id=1,
                invoice_date=date(2026, 3, 1),
                due_date=date(2026, 3, 15),
                items=[InvoiceItemIn(description="x")],
                bogus=1,
            )


# ── finance pure logic ─────────────────────────────────────────────────────

class TestStatusFor:
    def _inv(self, **kw) -> Invoice:
        inv = Invoice()
        inv.paid_amount = Decimal("0")
        inv.sent_at = None
        inv.due_date = date(2026, 1, 1)
        inv.total = Decimal("1000")
        inv.status = InvoiceStatus.DRAFT
        for k, v in kw.items():
            setattr(inv, k, v)
        return inv

    def test_draft(self):
        assert fin._status_for(self._inv(), date(2026, 2, 1)) is InvoiceStatus.DRAFT

    def test_sent(self):
        inv = self._inv(sent_at=True, due_date=date(2026, 2, 1))
        assert fin._status_for(inv, date(2026, 1, 5)) is InvoiceStatus.SENT

    def test_overdue(self):
        inv = self._inv(sent_at=True, due_date=date(2026, 1, 1))
        assert fin._status_for(inv, date(2026, 1, 15)) is InvoiceStatus.OVERDUE

    def test_partial(self):
        inv = self._inv(paid_amount=Decimal("500"))
        assert fin._status_for(inv, date(2026, 2, 1)) is InvoiceStatus.PARTIAL

    def test_paid(self):
        inv = self._inv(paid_amount=Decimal("1000"))
        assert fin._status_for(inv, date(2026, 2, 1)) is InvoiceStatus.PAID

    def test_cancelled_wins(self):
        inv = self._inv(status=InvoiceStatus.CANCELLED, paid_amount=Decimal("1000"))
        assert fin._status_for(inv, date(2026, 2, 1)) is InvoiceStatus.CANCELLED


class TestTotals:
    def test_totals_with_tax(self):
        items = [
            InvoiceItem(quantity=Decimal("2"), rate=Decimal("1000")),
            InvoiceItem(quantity=Decimal("1"), rate=Decimal("500")),
        ]
        sub, tax, total = fin._totals(items, Decimal("18"))
        assert sub == Decimal("2500.00")
        assert tax == Decimal("450.00")
        assert total == Decimal("2950.00")

    def test_totals_zero_items(self):
        sub, tax, total = fin._totals([], Decimal("18"))
        assert (sub, tax, total) == (Decimal("0.00"), Decimal("0.00"), Decimal("0.00"))


class TestPeriodBounds:
    def test_month_bound_invariants(self):
        start, end = fin._period_bounds("month")
        assert start.day == 1
        assert end > start
        assert end.day == 1

    def test_quarter_bound_invariant(self):
        start, end = fin._period_bounds("quarter")
        assert start.day == 1
        assert end > start

    def test_year_starts_jan1(self):
        start, end = fin._period_bounds("year")
        assert start.month == 1 and start.day == 1
        assert start.year == end.year - 1

    def test_all_generous_bounds(self):
        start, end = fin._period_bounds("all")
        assert start == date(1970, 1, 1)
        assert end.year == 9999

    def test_previous_all_is_none(self):
        assert fin._previous_bounds("all") is None

    def test_previous_months_adjacent(self):
        start, end = fin._previous_bounds("month")
        assert end > start
        assert start.day == 1


# ── clients schemas + logic ────────────────────────────────────────────────

class TestClientSchemas:
    def test_name_min_length(self):
        with pytest.raises(ValidationError):
            ClientCreate(name="x")

    def test_email_validation(self):
        with pytest.raises(ValidationError):
            ClientCreate(name="Acme", email="not-an-email")

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            ClientCreate(name="Acme", bogus=1)


class TestClientDict:
    def _client(self) -> Client:
        return Client(
            id=1,
            name="Acme",
            client_type=ClientType.COMPANY,
            deal_stage=DealStage.LEAD,
            budget_range="10-20L",
            is_active=True,
        )

    def test_financial_included_by_default(self):
        data = _client_dict(self._client())
        assert data["budget_range"] == "10-20L"

    def test_financial_stripped(self):
        data = _client_dict(self._client(), include_financial=False)
        assert "budget_range" not in data


# ── route assembly ─────────────────────────────────────────────────────────

class TestClientNameResolver:
    def test_default_resolver_is_noop(self):
        import asyncio

        from studioerp.rings.work.projects import service as ps

        result = asyncio.run(ps._client_names(None, {1, 2}))
        assert result == {}

    def test_app_registers_money_resolver(self):
        from studioerp.api.app import app  # noqa: F401 — triggers create_app wiring
        from studioerp.rings.work.projects import service as ps

        assert ps.client_name_resolver is not None


class TestMoneyRoutes:
    def test_money_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        for expected in (
            "/api/v1/clients",
            "/api/v1/finance/overview",
            "/api/v1/invoices",
            "/api/v1/expenses",
            "/api/v1/invoices/{invoice_id}/payment",
            "/api/v1/expenses/{expense_id}/approve",
            "/api/v1/clients/{client_id}/communications",
            "/api/v1/finance/projects/{project_id}/summary",
        ):
            assert expected in paths, f"missing route {expected}"


# ── project_financials (INR-aggregated per-project snapshot) ───────────────

class TestProjectFinancials:
    @staticmethod
    def _inv(total: str, paid: str, rate: str, status: InvoiceStatus = InvoiceStatus.SENT):
        inv = Invoice()
        inv.project_id = 1
        inv.total = Decimal(total)
        inv.paid_amount = Decimal(paid)
        inv.exchange_rate = Decimal(rate)
        inv.status = status
        return inv

    @staticmethod
    def _expense(amount: str, rate: str, status: ExpenseStatus = ExpenseStatus.APPROVED):
        exp = Expense()
        exp.project_id = 1
        exp.amount = Decimal(amount)
        exp.exchange_rate = Decimal(rate)
        exp.status = status
        return exp

    @staticmethod
    def _run(invoices, expenses, project_missing: bool = False):
        import asyncio

        from unittest.mock import AsyncMock

        from studioerp.errors import FinanceError
        from studioerp.rings.work.projects.models import Project

        class _Scalars:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        class _FakeResult:
            def __init__(self, rows):
                self._rows = rows

            def scalars(self):
                return _Scalars(self._rows)

        db = AsyncMock()
        if project_missing:
            db.get = AsyncMock(return_value=None)
            try:
                asyncio.run(fin.project_financials(db, 1))
            except FinanceError as exc:
                return exc
            raise AssertionError("expected FinanceError for a missing project")
        db.get = AsyncMock(return_value=Project(id=1, is_active=True))
        db.execute = AsyncMock(side_effect=[_FakeResult(invoices), _FakeResult(expenses)])
        return asyncio.run(fin.project_financials(db, 1))

    def test_missing_project_raises(self):
        exc = self._run([], [], project_missing=True)
        assert exc.status_code == 404

    def test_empty_project_zero_snapshot(self):
        data = self._run([], [])
        assert data == {
            "project_id": 1,
            "invoiced": Decimal("0.00"),
            "received": Decimal("0.00"),
            "outstanding": Decimal("0.00"),
            "expenses": Decimal("0.00"),
            "profit": Decimal("0.00"),
            "invoice_count": 0,
            "expense_count": 0,
        }

    def test_inr_invoices_pass_through(self):
        data = self._run(
            [self._inv("1000.00", "400.00", "1")],
            [self._expense("250.00", "1")],
        )
        assert data["invoiced"] == Decimal("1000.00")
        assert data["received"] == Decimal("400.00")
        assert data["outstanding"] == Decimal("600.00")
        assert data["expenses"] == Decimal("250.00")
        assert data["profit"] == Decimal("150.00")

    def test_foreign_currency_converted_at_stored_rate(self):
        data = self._run(
            [
                self._inv("1000.00", "0.00", "83.4"),
                self._inv("500.00", "500.00", "83.4"),
            ],
            [],
        )
        assert data["invoiced"] == Decimal("125100.00")
        assert data["received"] == Decimal("41700.00")
        assert data["outstanding"] == Decimal("83400.00")

    def test_received_past_total_is_not_negative(self):
        # Marked-paid invoices can carry paid == total; outstanding must floor at 0.
        data = self._run([self._inv("1000.00", "1000.00", "1")], [])
        assert data["outstanding"] == Decimal("0.00")

    def test_profit_is_received_minus_expenses(self):
        data = self._run(
            [self._inv("5000.00", "3000.00", "1")],
            [self._expense("400.00", "1"), self._expense("600.00", "1")],
        )
        assert data["profit"] == Decimal("2000.00")

    def test_invoice_and_expense_counts(self):
        data = self._run(
            [self._inv("100.00", "0.00", "1"), self._inv("200.00", "0.00", "1")],
            [self._expense("50.00", "1")],
        )
        assert data["invoice_count"] == 2
        assert data["expense_count"] == 1
