"""Audit logging (kernel k0).

The kernel owns the ``AuditLog`` table and the async :func:`log_audit` writer
so every ring can record tamper-evident action trails without depending on an
outer module. Correlation fields (request_id / ip / user agent) auto-fill from
the ambient request context; explicit arguments win.

Ported from the reference monolith ``app/modules/audit/models.py`` +
``service.py`` (audit is a k0 kernel primitive, not a ring module).
"""

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from studioerp.db.base import Base, TimestampMixin
from studioerp.request_context import current_request_context


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(40))
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(40))
    details: Mapped[dict | None] = mapped_column(JSON)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(255))


async def log_audit(
    db: AsyncSession,
    user,
    action: str,
    entity_type: str,
    *,
    entity_id: str | None = None,
    details: dict | None = None,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """Persist an audit record for a state-changing operation.

    ``request_id`` / ``ip_address`` / ``user_agent`` default to the values
    captured by the request-context middleware; pass them explicitly only for
    out-of-band operations (e.g. scheduled jobs). Does NOT commit; the caller
    commits alongside its own changes so the trail and the change are atomic.
    """
    ambient = current_request_context()
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=details,
            request_id=request_id if request_id is not None else ambient["request_id"],
            ip_address=ip_address if ip_address is not None else ambient["ip_address"],
            user_agent=user_agent if user_agent is not None else ambient["user_agent"],
        )
    )
