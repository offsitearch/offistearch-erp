"""Employee schemas (r2/people). Ported from ``app/modules/employees/schemas.py``.

Salary and department/org-level organisation schemas are intentionally omitted
here: salary lives in the money ring (r4), and Department/OrgLevel schemas are
owned by the platform org-structure module (Ring 1).
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from studioerp.enums import EmploymentType


class EmployeeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    contact_email: EmailStr | None = None
    employee_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = None
    org_level_id: int | None = None
    designation: str | None = Field(default=None, max_length=120)
    reporting_to_id: int | None = None
    date_of_joining: date | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=10)
    skills: list[str] | None = None
    employment_type: EmploymentType = EmploymentType.FULL_TIME
    is_active: bool = True


class EmployeeCreateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    employee_id: str | None
    email: EmailStr
    contact_email: str | None = None
    phone: str | None
    name: str
    department_id: int | None
    department: str | None = None
    org_level_id: int | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    reporting_to_id: int | None
    reports_to_name: str | None = None
    date_of_joining: date | None
    date_of_birth: date | None
    gender: str | None
    blood_group: str | None
    address: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    skills: list[str] | None
    employment_type: str
    is_active: bool
    created_at: datetime
    generated_password: str


class EmployeeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    contact_email: EmailStr | None = None
    employee_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    department_id: int | None = None
    org_level_id: int | None = None
    designation: str | None = Field(default=None, max_length=120)
    reporting_to_id: int | None = None
    date_of_joining: date | None = None
    date_of_birth: date | None = None
    gender: str | None = Field(default=None, max_length=10)
    blood_group: str | None = Field(default=None, max_length=5)
    address: str | None = None
    emergency_contact_name: str | None = Field(default=None, max_length=120)
    emergency_contact_phone: str | None = Field(default=None, max_length=20)
    skills: list[str] | None = None
    employment_type: EmploymentType | None = None
    is_active: bool | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    employee_id: str | None
    email: EmailStr
    contact_email: str | None = None
    phone: str | None
    name: str
    department_id: int | None
    department: str | None = None
    org_level_id: int | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    reporting_to_id: int | None
    reports_to_name: str | None = None
    date_of_joining: date | None
    date_of_birth: date | None
    gender: str | None
    blood_group: str | None
    address: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    skills: list[str] | None
    employment_type: str
    is_active: bool
    created_at: datetime


class EmployeeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: str | None
    name: str
    email: EmailStr
    contact_email: str | None = None
    department: str | None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    employment_type: str
    is_active: bool


class EmployeePage(BaseModel):
    items: list[EmployeeListItem]
    total: int
    page: int
    page_size: int


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    doc_type: str
    file_name: str
    uploaded_by: int | None
    uploaded_at: datetime


class OrgChartNode(BaseModel):
    user_id: int
    name: str
    employee_id: str | None
    designation: str | None
    department_id: int | None = None
    department_name: str | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    reports_to_id: int | None
    children: list["OrgChartNode"] = []
