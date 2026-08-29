"""Ring 1 (platform) tests — non-DB: schema validation + route assembly.

DB-backed behaviour is exercised once a test PostgreSQL is available; these
cover the pure validators and the API composition root so the ring stays green
without a live database (asyncpg has no Python 3.14 wheel).
"""

import pytest
from pydantic import ValidationError

from studioerp.platform.settings.schemas import SettingUpsertIn


class TestSettingUpsertKnownSettings:
    def test_valid_attendance_late_threshold(self):
        s = SettingUpsertIn(
            group="attendance", key="late_threshold_minutes", value={"value": 10}
        )
        assert s.value == {"value": 10}

    def test_rejects_wrong_type(self):
        with pytest.raises(ValidationError):
            SettingUpsertIn(
                group="attendance", key="late_threshold_minutes", value={"value": "10"}
            )

    def test_rejects_out_of_range_int(self):
        with pytest.raises(ValidationError):
            SettingUpsertIn(
                group="leave", key="casual_annual", value={"value": 200}
            )

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            SettingUpsertIn(
                group="leave", key="sick_annual", value={"value": -1}
            )

    def test_unknown_setting_not_validated(self):
        # Arbitrary keys outside the KNOWN_SETTINGS table are accepted as-is.
        s = SettingUpsertIn(group="company", key="profile", value={"name": "X"})
        assert s.value == {"name": "X"}


class TestAppAssembly:
    def test_ring1_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/departments" in paths
        assert "/api/v1/org-levels" in paths
        assert "/api/v1/settings" in paths
        assert "/api/v1/notifications" in paths
        assert "/api/v1/notifications/unread-count" in paths
