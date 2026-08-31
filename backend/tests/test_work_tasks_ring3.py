"""Ring 3 (work/tasks) tests — non-DB: schema validation + route assembly."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from studioerp.rings.work.tasks.schemas import ChecklistItemIn, TaskCreate, TaskUpdate


class TestTaskSchemas:
    def test_create_valid_minimal(self):
        t = TaskCreate(title="Prepare drawings")
        assert t.title == "Prepare drawings"
        assert t.priority.value == "medium"
        assert t.status.value == "todo"
        assert t.tags is None

    def test_create_valid_full(self):
        t = TaskCreate(
            title="Drawings",
            project_id=2,
            assigned_to=7,
            priority="high",
            estimated_hours=Decimal("4.5"),
            tags=["redline", "working"],
        )
        assert t.priority.value == "high"
        assert t.tags == ["redline", "working"]

    def test_create_rejects_empty_title(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="")

    def test_create_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            TaskCreate(title="X", oops=1)

    def test_update_all_optional(self):
        u = TaskUpdate(status="in_progress")
        assert u.status.value == "in_progress"
        assert u.title is None

    def test_checklist_item_requires_text(self):
        with pytest.raises(ValidationError):
            ChecklistItemIn(text="")


class TestTaskRoutes:
    def test_tasks_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        for expected in (
            "/api/v1/tasks",
            "/api/v1/tasks/board",
            "/api/v1/tasks/{task_id}",
            "/api/v1/tasks/{task_id}/checklist",
            "/api/v1/tasks/{task_id}/checklist/{item_id}",
        ):
            assert expected in paths, f"missing route {expected}"
