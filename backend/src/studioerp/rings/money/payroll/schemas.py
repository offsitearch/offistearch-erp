"""Payroll schemas (ring r4/money). Ported from ``app/modules/payroll/schemas.py``."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

_ADJ_KIND = "^(addition|deduction)$"
_ADJ_CATEGORY = "^(bonus|incentive|advance|penalty|other)$"


class PayrollAdjustmentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=_ADJ_KIND)
    category: str = Field(pattern=_ADJ_CATEGORY)
    label: str = Field(min_length=1, max_length=120)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class PayrollAdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    category: str
    label: str
    amount: Decimal
    created_by: int | None = None
    created_at: datetime | None = None


class PayrollEntryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    working_days: int | None = Field(default=None, ge=0)
    prorate: bool | None = None
    notes: str | None = Field(default=None, max_length=2000)


class AddEntriesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[int] = Field(min_length=1)


class RunCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: int = Field(ge=1, le=12)
    year: int = Field(ge=2020, le=2100)
    title: str = Field(default="", max_length=120)


class MarkPaidIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: str | None = Field(default=None, max_length=15)
    payment_reference: str | None = Field(default=None, max_length=60)


class PayrollEntryOut(BaseModel):
    user_id: int
    user_name: str | None = None
    employee_id: str | None = None
    designation: str | None = None
    department: str | None = None
    date_of_joining: date | None = None
    already_paid: bool = False
    working_days: int
    total_days: int
    prorate: bool = True
    basic_amount: Decimal
    hra_amount: Decimal
    special_amount: Decimal
    base_gross: Decimal
    pf_deduction: Decimal
    gross_salary: Decimal
    deductions: Decimal
    net_pay: Decimal
    entry_status: str = "included"
    notes: str | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    payment_ref: str | None = None
    paid_at: datetime | None = None
    additions_total: Decimal = Decimal("0")
    deductions_extra_total: Decimal = Decimal("0")
    adjustments: list[PayrollAdjustmentOut] = []


class PayrollRunOut(BaseModel):
    id: int
    title: str = ""
    month: int
    year: int
    status: str = "draft"
    created_by: int | None = None
    created_at: datetime | None = None
    processed_by: int | None = None
    processed_at: datetime | None = None
    paid_at: datetime | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    entries: list[PayrollEntryOut] = []
    total_gross: Decimal = Decimal("0")
    total_deductions: Decimal = Decimal("0")
    total_net: Decimal = Decimal("0")
    total_working_days: int = 0
    headcount: int = 0
    approved_count: int = 0


class PayrollMonthOut(BaseModel):
    month: int
    year: int
    runs: list[PayrollRunOut] = []
    preview: list[PayrollEntryOut] = []
    preview_total_net: Decimal = Decimal("0")
