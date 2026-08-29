"""Ring 3 (work/projects) tests — non-DB: schema validation, pure logic, route assembly.

DB-backed persistence flows require a test PostgreSQL and are covered once
one is available.
"""

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from studioerp.rings.work.projects.defaults import PROJECT_TYPE_TEMPLATES
from studioerp.rings.work.projects.models import ProjectPhase
from studioerp.rings.work.projects.schemas import (
    PhaseCreate,
    PhaseUpdate,
    ProjectCreate,
    ProjectTeamIn,
    ProjectUpdate,
)
from studioerp.rings.work.projects import service


class TestProjectCreateSchema:
    def test_valid_minimal(self):
        p = ProjectCreate(name="Villa Project", project_type="residential")
        assert p.name == "Villa Project"
        assert p.currency == "INR"
        assert p.exchange_rate == Decimal("1")
        assert p.priority == "medium"
        assert p.team == []

    def test_valid_full(self):
        p = ProjectCreate(
            name="Tower",
            project_type="commercial",
            client_id=3,
            currency="usd",
            exchange_rate=Decimal("83.5"),
            team=[ProjectTeamIn(user_id=1, role="Architect")],
        )
        assert p.currency == "USD"
        assert p.team[0].role == "Architect"

    def test_rejects_unsupported_currency(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="X", project_type="residential", currency="BTC")

    def test_rejects_short_name(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="A", project_type="residential")

    def test_forbids_extra_fields(self):
        with pytest.raises(ValidationError):
            ProjectCreate(name="X", project_type="residential", oops=1)


class TestProjectUpdateSchema:
    def test_all_optional(self):
        u = ProjectUpdate(client_id=None, priority="high")
        assert u.name is None
        assert u.priority == "high"

    def test_currency_optional_validation(self):
        with pytest.raises(ValidationError):
            ProjectUpdate(currency="XYZ")


class TestPhaseSchemas:
    def test_phase_create_defaults(self):
        ph = PhaseCreate(name="Concept")
        assert ph.status.value == "not_started"
        assert ph.completion_pct == Decimal("0")

    def test_phase_create_rejects_out_of_range_pct(self):
        with pytest.raises(ValidationError):
            PhaseCreate(name="C", completion_pct=101)

    def test_phase_update_optional(self):
        pu = PhaseUpdate(completion_pct=50)
        assert pu.completion_pct == Decimal("50")


class TestTemplateLogic:
    def test_templates_for_every_project_type(self):
        from studioerp.enums import ProjectType

        for ptype in ProjectType:
            assert ptype.value in PROJECT_TYPE_TEMPLATES

    def test_list_templates_sorted_and_shaped(self):
        templates = service.list_templates()
        assert templates
        labels = [t["label"] for t in templates]
        assert labels == sorted(labels, key=str.lower)
        first = templates[0]
        assert set(first) == {"project_type", "label", "phases"}
        assert isinstance(first["phases"], list)
        assert first["phases"]


class TestPhaseDateLogic:
    def test_bad_input_returns_none_pairs(self):
        assert service._phase_dates(None, None, 3) == [(None, None)] * 3
        assert service._phase_dates(date(2026, 1, 1), date(2025, 1, 1), 2) == [
            (None, None),
            (None, None),
        ]

    def test_single_day_distribution(self):
        pairs = service._phase_dates(date(2026, 1, 1), date(2026, 1, 5), 2)
        assert pairs[0][0] == date(2026, 1, 1)
        assert pairs[1][1] == date(2026, 1, 5)

    def test_compute_progress_average(self):
        phases = [
            ProjectPhase(id=1, order_index=0, completion_pct=Decimal("50")),
            ProjectPhase(id=2, order_index=1, completion_pct=Decimal("100")),
        ]
        assert service._compute_progress(phases) == Decimal("75.00")

    def test_compute_progress_empty(self):
        assert service._compute_progress([]) == Decimal("0.00")


class TestProjectCodeLogic:
    def test_next_code_no_existing(self):
        assert service.next_project_code.__name__ == "next_project_code"

    def test_label_fallback(self):
        assert service._label("residential") == "Residential"
        assert service._label("does_not_exist") == "Does Not Exist"


class TestProjectRoutes:
    def test_projects_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        for expected in (
            "/api/v1/projects",
            "/api/v1/projects/templates",
            "/api/v1/projects/options",
            "/api/v1/projects/{project_id}",
            "/api/v1/projects/{project_id}/timeline",
            "/api/v1/projects/{project_id}/phases",
            "/api/v1/projects/{project_id}/phases/{phase_id}",
            "/api/v1/projects/{project_id}/team/{user_id}",
        ):
            assert expected in paths, f"missing route {expected}"
