"""Ring 2 (people/employees) tests — non-DB: schema validation + route assembly.

DB-backed flows are exercised once a test PostgreSQL is available.
"""

import pytest
from pydantic import ValidationError

from studioerp.rings.people.employees.schemas import EmployeeCreate, EmployeeUpdate
from studioerp.enums import EmploymentType


class TestEmployeeSchemas:
    def test_create_requires_name(self):
        emp = EmployeeCreate(name="Aarav Mehta", designation="Architect")
        assert emp.name == "Aarav Mehta"
        assert emp.employment_type == EmploymentType.FULL_TIME

    def test_create_rejects_short_name(self):
        with pytest.raises(ValidationError):
            EmployeeCreate(name="A", designation="Architect")

    def test_create_forbids_unknown_fields(self):
        with pytest.raises(ValidationError):
            EmployeeCreate(name="Aarav Mehta", unexpected_field=1)

    def test_update_optional_fields(self):
        upd = EmployeeUpdate(phone="+911234567890")
        assert upd.phone == "+911234567890"
        assert upd.name is None


class TestEmployeeRoutes:
    def test_employee_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/employees" in paths
        assert "/api/v1/employees/org-chart" in paths
        assert "/api/v1/employees/skills" in paths
        assert "/api/v1/employees/designations" in paths
        assert "/api/v1/employees/{user_id}" in paths
        assert "/api/v1/employees/{user_id}/documents" in paths
