"""Unit tests for kernel state-machine transition guards.

Unit-level counterpart of the reference API-integration suite
``test_state_machines.py`` — pins the same valid/invalid transition tables
without a database or running app.
"""

import pytest

from studioerp.enums import (
    ExpenseStatus,
    LeaveStatus,
    MeetingStatus,
    ProjectStatus,
    SiteVisitStatus,
    TaskStatus,
    TimesheetStatus,
)
from studioerp.errors import FinanceError, ProjectError, TaskError
from studioerp.state_machines import assert_transition


class TestTaskTransitions:
    def test_in_progress_to_done_valid(self):
        assert_transition(TaskStatus.IN_PROGRESS, TaskStatus.DONE)  # no raise

    def test_done_to_todo_invalid(self):
        with pytest.raises(TaskError):
            assert_transition(TaskStatus.DONE, TaskStatus.TODO)

    def test_todo_to_done_invalid(self):
        with pytest.raises(TaskError):
            assert_transition(TaskStatus.TODO, TaskStatus.DONE)

    def test_todo_to_in_progress_valid(self):
        assert_transition(TaskStatus.TODO, TaskStatus.IN_PROGRESS)


class TestExpenseTransitions:
    def test_approved_expense_cannot_be_rejected(self):
        with pytest.raises(FinanceError):
            assert_transition(ExpenseStatus.APPROVED, ExpenseStatus.REJECTED)

    def test_pending_to_approved_valid(self):
        assert_transition(ExpenseStatus.PENDING, ExpenseStatus.APPROVED)


class TestProjectTransitions:
    def test_completed_is_terminal(self):
        with pytest.raises(ProjectError):
            assert_transition(ProjectStatus.COMPLETED, ProjectStatus.ON_HOLD)

    def test_design_to_under_review_valid(self):
        assert_transition(ProjectStatus.DESIGN, ProjectStatus.UNDER_REVIEW)


class TestLeaveTransitions:
    def test_approved_leave_is_terminal(self):
        with pytest.raises(Exception):
            assert_transition(LeaveStatus.APPROVED, LeaveStatus.PENDING)

    def test_pending_to_approved_valid(self):
        assert_transition(LeaveStatus.PENDING, LeaveStatus.APPROVED)


class TestTimesheetTransitions:
    def test_draft_to_submitted_valid(self):
        assert_transition(TimesheetStatus.DRAFT, TimesheetStatus.SUBMITTED)

    def test_approved_is_terminal(self):
        with pytest.raises(Exception):
            assert_transition(TimesheetStatus.APPROVED, TimesheetStatus.DRAFT)


class TestMeetingTransitions:
    def test_scheduled_to_cancelled_valid(self):
        assert_transition(MeetingStatus.SCHEDULED, MeetingStatus.CANCELLED)

    def test_completed_meeting_is_terminal(self):
        with pytest.raises(Exception):
            assert_transition(MeetingStatus.COMPLETED, MeetingStatus.SCHEDULED)


class TestSiteVisitTransitions:
    def test_scheduled_to_completed_valid(self):
        assert_transition(SiteVisitStatus.SCHEDULED, SiteVisitStatus.COMPLETED)

    def test_completed_site_visit_is_terminal(self):
        with pytest.raises(Exception):
            assert_transition(SiteVisitStatus.COMPLETED, SiteVisitStatus.SCHEDULED)
