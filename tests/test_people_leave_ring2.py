"""Ring 2 (people/leave) tests — non-DB: pure policy logic + route assembly.

DB-backed flows (balance persistence, approval atomic increments, JSONB policy
merge) require a test PostgreSQL and are covered once one is available.
"""

from datetime import date
from decimal import Decimal

from studioerp.rings.people.leave.service import working_day_count


class TestWorkingDayCount:
    def test_weekdays_only(self):
        # Mon 2026-01-05 .. Fri 2026-01-09 (Mon-Fri)
        days = working_day_count(date(2026, 1, 5), date(2026, 1, 9), set(), False, False)
        assert days == Decimal("5.00")

    def test_excludes_weekend(self):
        # Sat 2026-01-03 .. Sun 2026-01-11
        days = working_day_count(date(2026, 1, 3), date(2026, 1, 11), set(), False, False)
        assert days == Decimal("5.00")

    def test_excludes_holidays(self):
        holidays = {date(2026, 1, 5)}
        days = working_day_count(date(2026, 1, 5), date(2026, 1, 9), holidays, False, False)
        assert days == Decimal("4.00")

    def test_half_day_first(self):
        days = working_day_count(date(2026, 1, 5), date(2026, 1, 6), set(), True, False)
        assert days == Decimal("1.50")

    def test_full_week_with_two_half_days(self):
        days = working_day_count(date(2026, 1, 5), date(2026, 1, 9), set(), True, True)
        assert days == Decimal("4.00")

    def test_no_working_days_clamps_to_zero(self):
        # A Saturday-Sunday span has no working days.
        days = working_day_count(date(2026, 1, 3), date(2026, 1, 4), set(), False, False)
        assert days == Decimal("0.00")


class TestLeaveRoutes:
    def test_leave_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/leaves" in paths
        assert "/api/v1/leaves/balance" in paths
        assert "/api/v1/leaves/mine" in paths
        assert "/api/v1/leaves/pending" in paths
        assert "/api/v1/leaves/team-availability" in paths
        assert "/api/v1/leaves/{leave_id}/approve" in paths
        assert "/api/v1/leaves/{leave_id}/reject" in paths
