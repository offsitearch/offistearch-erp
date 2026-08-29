"""Ring 3 (work/timesheets) tests — non-DB: schema validation, pure logic, route assembly."""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from studioerp.enums import TimesheetStatus
from studioerp.rings.work.timesheets import service
from studioerp.rings.work.timesheets.models import TimesheetDay
from studioerp.rings.work.timesheets.schemas import (
    RejectRequest,
    TimesheetEntryIn,
    TimesheetWeekSave,
)


class TestEntrySchemas:
    def test_valid_entry(self):
        e = TimesheetEntryIn(project_id=1, date=date(2026, 1, 5), hours=Decimal("7.5"))
        assert e.hours == Decimal("7.5")
        assert e.location is None

    def test_rejects_zero_hours(self):
        with pytest.raises(ValidationError):
            TimesheetEntryIn(date=date(2026, 1, 5), hours=Decimal("0"))

    def test_rejects_descriptions_too_long(self):
        with pytest.raises(ValidationError):
            TimesheetEntryIn(date=date(2026, 1, 5), hours=Decimal("1"), description="x" * 501)

    def test_week_save_empty_entries_allowed(self):
        w = TimesheetWeekSave(week_start=date(2026, 1, 5))
        assert w.entries == []

    def test_reject_reason_min_length(self):
        with pytest.raises(ValidationError):
            RejectRequest(reason="ab")


class TestWeekLogic:
    def test_monday_of(self):
        assert service.monday_of(date(2026, 1, 8)) == date(2026, 1, 5)  # Thu -> Mon
        assert service.monday_of(date(2026, 1, 5)) == date(2026, 1, 5)  # Mon stays

    def test_week_end(self):
        assert service.week_end_of(date(2026, 1, 5)) == date(2026, 1, 11)

    def test_aggregate_submitted_wins(self):
        days = {
            date(2026, 1, 5): TimesheetDay(date=date(2026, 1, 5), status=TimesheetStatus.SUBMITTED),
            date(2026, 1, 6): TimesheetDay(date=date(2026, 1, 6), status=TimesheetStatus.APPROVED),
        }
        assert service._aggregate_status(days) == TimesheetStatus.SUBMITTED

    def test_aggregate_all_approved(self):
        days = {
            date(2026, 1, 5): TimesheetDay(date=date(2026, 1, 5), status=TimesheetStatus.APPROVED),
            date(2026, 1, 6): TimesheetDay(date=date(2026, 1, 6), status=TimesheetStatus.APPROVED),
        }
        assert service._aggregate_status(days) == TimesheetStatus.APPROVED

    def test_aggregate_rejected(self):
        days = {
            date(2026, 1, 5): TimesheetDay(date=date(2026, 1, 5), status=TimesheetStatus.REJECTED),
            date(2026, 1, 6): TimesheetDay(date=date(2026, 1, 6), status=TimesheetStatus.DRAFT),
        }
        assert service._aggregate_status(days) == TimesheetStatus.REJECTED

    def test_aggregate_mixed_draft(self):
        days = {
            date(2026, 1, 5): TimesheetDay(date=date(2026, 1, 5), status=TimesheetStatus.DRAFT),
            date(2026, 1, 6): TimesheetDay(date=date(2026, 1, 6), status=TimesheetStatus.APPROVED),
        }
        assert service._aggregate_status(days) == TimesheetStatus.DRAFT

    def test_aggregate_empty(self):
        assert service._aggregate_status({}) == TimesheetStatus.DRAFT

    def test_editable_day(self):
        draft = TimesheetDay(status=TimesheetStatus.DRAFT)
        rejected = TimesheetDay(status=TimesheetStatus.REJECTED)
        approved = TimesheetDay(status=TimesheetStatus.APPROVED)
        assert service._is_editable_day(draft)
        assert service._is_editable_day(rejected)
        assert not service._is_editable_day(approved)
        assert service._is_editable_day(None)


class TestTimesheetRoutes:
    def test_timesheet_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        for expected in (
            "/api/v1/timesheets",
            "/api/v1/timesheets/week",
            "/api/v1/timesheets/mine",
            "/api/v1/timesheets/pending",
            "/api/v1/timesheets/{timesheet_id}",
            "/api/v1/timesheets/{timesheet_id}/submit",
            "/api/v1/timesheets/{timesheet_id}/approve",
            "/api/v1/timesheets/{timesheet_id}/reject",
            "/api/v1/timesheets/{timesheet_id}/days/{day}/submit",
            "/api/v1/timesheets/{timesheet_id}/days/{day}/approve",
            "/api/v1/timesheets/{timesheet_id}/days/{day}/reject",
        ):
            assert expected in paths, f"missing route {expected}"
