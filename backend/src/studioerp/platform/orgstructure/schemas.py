"""Org structure schemas (k1).

The Department payload/out schemas that the reference monolith kept in the
employees module are consolidated here, because departments belong to the
org-structure ring; the employees ring imports them from here (cleaner ring
ownership, no cross-ring schema import).
"""

from pydantic import BaseModel, ConfigDict, Field


class DepartmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    parent_id: int | None = None
    head_id: int | None = None
    description: str | None = None


class DepartmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    parent_id: int | None = None
    head_id: int | None = None
    description: str | None = None
    is_active: bool | None = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None = None
    parent_name: str | None = None
    head_id: int | None
    description: str | None
    is_active: bool
    head_name: str | None = None
    member_count: int = 0


class OrgLevelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=8, pattern=r"^L\d{1,2}$")
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    rank: int = Field(default=0, ge=0, le=99)


class OrgLevelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=255)
    rank: int | None = Field(default=None, ge=0, le=99)
    is_active: bool | None = None


class OrgLevelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None
    rank: int
    is_active: bool
