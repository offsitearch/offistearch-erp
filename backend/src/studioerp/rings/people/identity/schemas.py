"""Identity schemas (r2). Ported from ``app/modules/identity/{schemas,users_admin}.py``."""

from datetime import date
import re

from pydantic import BaseModel, ConfigDict, EmailStr, Field

_PASSWORD_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d).{8,128}$")


def _validate_password(value: str) -> str:
    if not _PASSWORD_RE.match(value):
        raise ValueError(
            "Password must be 8-128 characters and include at least one letter and one number"
        )
    return value


class LoginRequest(BaseModel):
    user_id: str = Field(pattern=r"^\d{6}$", description="6-digit user login ID (YY####)")
    password: str = Field(min_length=6)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    employee_id: str | None
    email: EmailStr
    contact_email: str | None = None
    name: str
    department_id: int | None
    org_level_id: int | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    must_change_password: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


class RegeneratedCredentials(BaseModel):
    """One-time view of a freshly generated password. Never persisted."""

    login_id: str
    name: str
    generated_password: str


class UserCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    contact_email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    department_id: int | None = None
    org_level_id: int | None = None
    designation: str | None = Field(default=None, max_length=120)
    employee_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    date_of_joining: date | None = None


class UserUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    contact_email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)
    department_id: int | None = None
    org_level_id: int | None = None
    designation: str | None = Field(default=None, max_length=120)
    employee_id: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=20)
    is_active: bool | None = None


class UserBriefOut(BaseModel):
    id: int
    login_id: str
    employee_id: str | None
    name: str
    email: EmailStr
    contact_email: str | None = None
    department_id: int | None
    department: str | None
    org_level_id: int | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    is_active: bool
    must_change_password: bool = False


class UserAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login_id: str
    employee_id: str | None
    name: str
    email: EmailStr
    contact_email: str | None = None
    department_id: int | None
    department: str | None
    org_level_id: int | None = None
    org_level_code: str | None = None
    org_level_name: str | None = None
    designation: str | None
    is_active: bool
    must_change_password: bool = False
    phone: str | None = None
    date_of_joining: date | None = None


class UserAdminCreateOut(UserAdminOut):
    generated_password: str
