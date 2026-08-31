"""Ring 2 (people/attendance) tests — non-DB: pure policy logic + route assembly.

DB-backed flows (clock-in/out persistence, JSONB settings merge) require a test
PostgreSQL and are covered once one is available.
"""

from datetime import datetime, time

from studioerp.enums import AttendanceStatus
from studioerp.rings.people.attendance.service import (
    _minutes_between,
    _parse_time,
    compute_check_in_status,
    compute_total_hours,
)

WORKING_HOURS = {"start": "09:00", "end": "18:00", "min_hours": 8}
LATE_POLICY = {
    "grace_minutes": 15,
    "late_threshold": "09:15",
    "half_day_threshold": "11:00",
}


def _at(hh: int, mm: int) -> datetime:
    return datetime(2026, 1, 2, hh, mm)


class TestComputeCheckInStatus:
    def test_on_time_is_present(self):
        status, late = compute_check_in_status(_at(9, 0), WORKING_HOURS, LATE_POLICY)
        assert status is AttendanceStatus.PRESENT
        assert late == 0

    def test_within_grace_is_present(self):
        status, late = compute_check_in_status(_at(9, 15), WORKING_HOURS, LATE_POLICY)
        assert status is AttendanceStatus.PRESENT
        assert late == 0

    def test_late_before_half_day(self):
        status, late = compute_check_in_status(_at(9, 30), WORKING_HOURS, LATE_POLICY)
        assert status is AttendanceStatus.LATE
        assert late == 30

    def test_past_half_day_threshold(self):
        status, late = compute_check_in_status(_at(11, 30), WORKING_HOURS, LATE_POLICY)
        assert status is AttendanceStatus.HALF_DAY
        assert late == 150

    def test_minutes_are_zero_floor(self):
        status, late = compute_check_in_status(_at(8, 30), WORKING_HOURS, LATE_POLICY)
        assert late == 0


class TestComputeTotalHours:
    def test_elapsed_hours(self):
        hours = compute_total_hours(_at(9, 0), _at(17, 0), WORKING_HOURS)
        assert hours == 8

    def test_rounds_to_two_decimals(self):
        hours = compute_total_hours(_at(9, 5), _at(17, 0), WORKING_HOURS)
        assert str(hours) == "7.92"

    def test_zero_minimum(self):
        hours = compute_total_hours(_at(17, 0), _at(9, 0), WORKING_HOURS)
        assert str(hours) == "0.0"


class TestHelpers:
    def test_parse_time(self):
        assert _parse_time("09:15") == time(9, 15)

    def test_minutes_between(self):
        assert _minutes_between(time(9, 30), time(9, 0)) == 30
        assert _minutes_between(time(8, 0), time(9, 0)) == 0


class TestAttendanceRoutes:
    def test_attendance_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/attendance/check-in" in paths
        assert "/api/v1/attendance/check-out" in paths
        assert "/api/v1/attendance/me" in paths
        assert "/api/v1/attendance/today" in paths
        assert "/api/v1/attendance/bulk" in paths
        assert "/api/v1/attendance/report" in paths
        assert "/api/v1/attendance/{record_id}" in paths
