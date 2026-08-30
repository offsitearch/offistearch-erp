"""Report output schemas (ring r5/comms).

The report endpoints return plain JSON dicts (matching the reference monolith)
so the router does not attach ``response_model`` to them; these models document
the exact shapes of the JSON payloads so callers know what to expect.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProjectRowOut(BaseModel):
    model_config = ConfigDict()

    project_code: str
    name: str
    client_name: str | None
    project_type: str
    status: str
    progress_pct: Decimal
    budget: Decimal
    studio_fee: Decimal
    expenses: Decimal
    hours_logged: int


class ProjectSummaryOut(BaseModel):
    model_config = ConfigDict()

    total_projects: int
    active_projects: int
    total_budget: Decimal
    total_studio_fee: Decimal
    total_expenses: Decimal
    total_hours: int


class ProjectReportOut(BaseModel):
    model_config = ConfigDict()

    title: str
    summary: ProjectSummaryOut
    rows: list[ProjectRowOut]


class InvoiceRowOut(BaseModel):
    model_config = ConfigDict()

    invoice_number: str
    client_name: str | None
    invoice_date: date
    due_date: date
    total: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    status: str
    currency: str


class AgingOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    d0_30: Decimal = Field(alias="0_30")
    d31_60: Decimal = Field(alias="31_60")
    d61_90: Decimal = Field(alias="61_90")
    d90_plus: Decimal = Field(alias="90_plus")


class ExpenseRowOut(BaseModel):
    model_config = ConfigDict()

    category: str
    amount: Decimal


class FinanceSummaryOut(BaseModel):
    model_config = ConfigDict()

    period: str
    from_: date
    to: date
    invoiced: Decimal
    received: Decimal
    outstanding: Decimal
    expenses: Decimal
    profit: Decimal
    invoice_count: int


class FinanceReportOut(BaseModel):
    model_config = ConfigDict()

    title: str
    summary: FinanceSummaryOut
    rows: list[InvoiceRowOut]
    expense_rows: list[ExpenseRowOut]
    aging: AgingOut


class HrRowOut(BaseModel):
    model_config = ConfigDict()

    employee_id: str | None
    name: str
    department: str | None
    designation: str | None
    org_level_code: str | None
    present_days: int
    absent_days: int
    attendance_pct: float | None
    leave_days_ytd: float


class HeadcountDeptOut(BaseModel):
    model_config = ConfigDict()

    department: str
    count: int


class HeadcountLevelOut(BaseModel):
    model_config = ConfigDict()

    level: str
    count: int


class HrSummaryOut(BaseModel):
    model_config = ConfigDict()

    month: int
    year: int
    total_employees: int
    total_present_days: int
    total_absent_days: int
    avg_attendance_pct: float | None


class HrReportOut(BaseModel):
    model_config = ConfigDict()

    title: str
    summary: HrSummaryOut
    rows: list[HrRowOut]
    headcount_dept: list[HeadcountDeptOut]
    headcount_level: list[HeadcountLevelOut]


class TimesheetRowOut(BaseModel):
    model_config = ConfigDict()

    project_code: str | None
    project_name: str
    employee_id: str | None
    employee_name: str
    hours: float


class TimesheetCalendarDayOut(BaseModel):
    model_config = ConfigDict()

    date: str
    day: str
    hours: float
    status: str


class TimesheetGroupRowOut(BaseModel):
    model_config = ConfigDict()

    date: str | None
    project: str
    description: str | None
    location: str | None
    hours: float


class TimesheetGroupOut(BaseModel):
    model_config = ConfigDict()

    label: str
    hours: float
    rows: list[TimesheetGroupRowOut]


class TimesheetEmployeeOut(BaseModel):
    model_config = ConfigDict()

    user_id: int
    employee_id: str | None
    employee_name: str
    department: str | None
    total_hours: float
    groups: list[TimesheetGroupOut]
    approved_by_name: str = ""
    calendar: list[TimesheetCalendarDayOut] = []


class TimesheetSummaryOut(BaseModel):
    model_config = ConfigDict()

    from_: str
    to: str
    group_by: str
    total_hours: float
    employees: int
    projects: int
    periods: int


class TimesheetReportOut(BaseModel):
    model_config = ConfigDict()

    title: str
    summary: TimesheetSummaryOut
    rows: list[TimesheetRowOut]
    employees: list[TimesheetEmployeeOut]


class TimesheetOptionOut(BaseModel):
    model_config = ConfigDict()

    id: int
    name: str
    employee_id: str | None
    department: str | None