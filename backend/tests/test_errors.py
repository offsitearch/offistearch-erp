"""Unit tests for kernel domain-error hierarchy."""

from studioerp.errors import (
    DomainError,
    FinanceError,
    ProjectError,
    TaskError,
    to_http_status,
)


def test_domain_error_defaults_to_conflict():
    err = DomainError("boom")
    assert err.message == "boom"
    assert err.status_code == 409


def test_custom_status_code():
    err = FinanceError("nope", 422)
    assert err.status_code == 422


def test_subclass_carries_message():
    err = TaskError("cannot transition")
    assert isinstance(err, DomainError)
    assert err.message == "cannot transition"
    assert err.status_code == 409


def test_to_http_status_fallback():
    assert to_http_status(ProjectError("x", 400)) == 400
    assert to_http_status(DomainError("y")) == 409
