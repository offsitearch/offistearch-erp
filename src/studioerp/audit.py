"""Audit record building (kernel k0).

The kernel provides the pure side of audit logging: given a user/actor and an
action, build the record dict with the ambient request context filled in. The
DB-persisting writer (``log_audit``) lives in the audit ring module and uses
``build_audit_record`` + an ORM model.

Ported from the reference monolith ``app/modules/audit/service.py`` (the pure
part) and ``app/core/request_context.py``.
"""

from typing import Any

from studioerp.request_context import current_request_context


def build_audit_record(
    user,
    action: str,
    entity_type: str,
    *,
    entity_id: str | None = None,
    details: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    """Build an audit-record dict, filling correlation fields from ambient
    request context unless the caller overrides them.

    ``user`` may be ``None`` (system/anonymous actions). ``entity_id`` is
    stringified; ``details`` is stored as-is (JSON-serializable).
    """
    ambient = current_request_context()
    return {
        "user_id": user.id if user else None,
        "action": action,
        "entity_type": entity_type,
        "entity_id": str(entity_id) if entity_id is not None else None,
        "details": details,
        "request_id": request_id if request_id is not None else ambient["request_id"],
        "ip_address": ip_address if ip_address is not None else ambient["ip_address"],
        "user_agent": user_agent if user_agent is not None else ambient["user_agent"],
    }
