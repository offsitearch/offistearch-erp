"""Identity (r2): auth workflows on top of the platform User/RefreshToken models.

Owns the auth flows: login, token issuance/rotation, logout, password change,
user CRUD and credential resets. The persistent ``users``/``refresh_tokens``
tables live in the platform ring (ADR-0006); this module implements behaviour.
"""
