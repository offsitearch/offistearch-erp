"""Unit tests for kernel security primitives + config production guard.

Ports the pure contracts from the reference suite ``test_security.py``
(password hashing, token iss/aud/tvp, user-ID generation, prod guard).
API-level flows (login rate limiting, /auth/me staleness) live in the identity
ring tests, not the kernel.
"""

import jwt
import pytest

from studioerp.config import Settings, settings
from studioerp.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    format_login_id,
    generate_numeric_password,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_roundtrip(self):
        hashed = hash_password("s3cret!")
        assert hashed != "s3cret!"
        assert verify_password("s3cret!", hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_salts_are_unique(self):
        assert hash_password("same") != hash_password("same")


class TestUserIDGeneration:
    def test_format_login_id(self):
        assert format_login_id(2026, 1) == "260001"
        assert format_login_id(2026, 9999) == "269999"

    def test_format_login_id_caps_sequence(self):
        assert len(format_login_id(2026, 20000)) == 6

    def test_numeric_password_is_digits(self):
        pwd = generate_numeric_password()
        assert len(pwd) == 6
        assert pwd.isdigit()


class TestTokens:
    def test_access_token_carries_iss_aud_type_tvp(self):
        token = create_access_token(7, "L2", token_version=3)
        decoded = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        assert decoded["sub"] == "7"
        assert decoded["level"] == "L2"
        assert decoded["type"] == "access"
        assert decoded["tvp"] == 3
        assert decoded["iss"] == settings.jwt_issuer
        assert decoded["aud"] == settings.jwt_audience

    def test_refresh_token_carries_type_and_is_refresh(self):
        token, jti, expire = create_refresh_token(1)
        decoded = decode_token(token)
        assert decoded["type"] == "refresh"
        assert decoded["jti"] == jti
        assert decoded["sub"] == "1"

    def test_decode_rejects_wrong_audience(self):
        bad = jwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": 9999999999,
                "iss": settings.jwt_issuer,
                "aud": "other-app",
            },
            settings.secret_key,
            algorithm=settings.algorithm,
        )
        with pytest.raises(Exception):
            decode_token(bad)


class TestConfigProductionGuard:
    def test_rejects_default_secret(self):
        with pytest.raises(ValueError, match="SECRET_KEY"):
            Settings(
                _env_file=None,
                environment="production",
                secret_key="change-me-in-production",
            )

    def test_rejects_default_password(self):
        with pytest.raises(ValueError, match="FIRST_SUPERUSER_PASSWORD"):
            Settings(
                _env_file=None,
                environment="production",
                secret_key="s3cr3t-r4nd0m-key",
                first_superuser_password="change-me",
            )

    def test_allows_strong_config(self):
        cfg = Settings(
            _env_file=None,
            environment="production",
            secret_key="s3cr3t-r4nd0m-key-1234",
            first_superuser_password="Pr0duction!Pwd",
        )
        assert cfg.environment == "production"
