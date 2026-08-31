"""Ring 2 (people/holidays) tests — non-DB: schema validation + route assembly.

DB-backed persistence flows require a test PostgreSQL and are covered once
one is available.
"""

import pytest
from pydantic import ValidationError

from studioerp.rings.people.holidays.schemas import HolidayCreate, HolidayUpdate
from datetime import date


class TestHolidaySchemas:
    def test_create_valid(self):
        h = HolidayCreate(name="Republic Day", date=date(2026, 1, 26))
        assert h.name == "Republic Day"
        assert h.is_recurring is False
        assert h.applicable_to == "all"

    def test_create_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            HolidayCreate(name="H", date=date(2026, 1, 1), oops=1)

    def test_create_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            HolidayCreate(name="", date=date(2026, 1, 1))

    def test_update_all_optional(self):
        u = HolidayUpdate(is_recurring=True)
        assert u.is_recurring is True
        assert u.name is None


class TestHolidayRoutes:
    def test_holiday_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/holidays" in paths
        assert "/api/v1/holidays/{holiday_id}" in paths
