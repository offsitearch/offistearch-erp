"""Ring 2 (people/identity) tests — non-DB: rate-limiter, schema validation,
route assembly. DB-backed flows are exercised once a test PostgreSQL is available.
"""

import pytest
from pydantic import ValidationError

from studioerp.rings.people.identity.rate_limit import (
    check_blocked,
    record_failure,
    record_success,
    reset_rate_limits,
)
from studioerp.rings.people.identity.schemas import LoginRequest


class TestRateLimiter:
    def setup_method(self):
        reset_rate_limits()

    def test_allows_under_limit(self):
        allowed, _ = record_failure("1.2.3.4", 5, 300)
        assert allowed is True

    def test_blocks_after_max_attempts(self):
        for _ in range(5):
            record_failure("key1", 5, 300)
        blocked, retry = check_blocked("key1", 5, 300)
        assert blocked is True
        assert retry >= 1

    def test_record_failure_returns_allowed_false_at_cap(self):
        for _ in range(5):
            record_failure("key2", 5, 300)
        # Hammering past the cap does not inflate the window.
        allowed, retry = record_failure("key2", 5, 300)
        assert allowed is False
        assert retry >= 1

    def test_success_resets_bucket(self):
        for _ in range(5):
            record_failure("key3", 5, 300)
        record_success("key3")
        blocked, _ = check_blocked("key3", 5, 300)
        assert blocked is False

    def test_window_expiry_prunes(fast_window=1):
        for _ in range(5):
            record_failure("key4", 5, 1)
        import time

        time.sleep(1.1)
        blocked, _ = check_blocked("key4", 5, 1)
        assert blocked is False


class TestLoginSchema:
    def test_accepts_six_digit_login_id(self):
        req = LoginRequest(user_id="260001", password="supersecret1")
        assert req.user_id == "260001"

    def test_rejects_bad_login_id_format(self):
        with pytest.raises(ValidationError):
            LoginRequest(user_id="abc", password="supersecret1")

    def test_rejects_short_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(user_id="260001", password="123")


class TestIdentityRoutes:
    def test_auth_and_users_routes_registered(self):
        from studioerp.api.app import app

        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/v1/auth/login" in paths
        assert "/api/v1/auth/refresh" in paths
        assert "/api/v1/auth/me" in paths
        assert "/api/v1/auth/change-password" in paths
        assert "/api/v1/users" in paths
        assert "/api/v1/users/{user_id}/regenerate-password" in paths
