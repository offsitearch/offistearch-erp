"""Ring 3 (work/site_visits) tests — non-DB: schema validation, route assembly."""

from datetime import date

import pytest
from pydantic import ValidationError

from studioerp.enums import SiteVisitStatus
from studioerp.rings.work.site_visits.schemas import SiteVisitCreate, SiteVisitUpdate


class TestCreateSchema:
    def test_valid(self):
        s = SiteVisitCreate(project_id=1, visit_date=date(2026, 2, 3))
        assert s.status == SiteVisitStatus.SCHEDULED
        assert s.weather is None

    def test_default_status_scheduled(self):
        s = SiteVisitCreate(project_id=1, visit_date=date(2026, 2, 3))
        assert s.status is SiteVisitStatus.SCHEDULED

    def test_extra_forbidden(self):
        with pytest.raises(ValidationError):
            SiteVisitCreate(project_id=1, visit_date=date(2026, 2, 3), bogus=1)

    def test_location_max_length(self):
        with pytest.raises(ValidationError):
            SiteVisitCreate(
                project_id=1, visit_date=date(2026, 2, 3), location="x" * 256
            )

    def test_weather_max_length(self):
        with pytest.raises(ValidationError):
            SiteVisitCreate(project_id=1, visit_date=date(2026, 2, 3), weather="x" * 81)


class TestUpdateSchema:
    def test_optional_all(self):
        s = SiteVisitUpdate()
        dumped = s.model_dump(exclude_unset=True)
        assert dumped == {}

    def test_status_membership(self):
        with pytest.raises(ValidationError):
            SiteVisitUpdate(status="nonsense")


class TestSiteVisitRoutes:
    def test_site_visit_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/site-visits" in paths
        assert "/api/v1/site-visits/{visit_id}" in paths

    def test_work_routes_present(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        for expected in (
            "/api/v1/projects",
            "/api/v1/tasks",
            "/api/v1/timesheets",
            "/api/v1/site-visits",
        ):
            assert expected in paths, f"missing route {expected}"
