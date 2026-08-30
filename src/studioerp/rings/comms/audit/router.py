"""Audit log viewing and export routes (ring comms/audit).

Endpoints: /audit-logs — list, filter, and CSV/XLSX-export audit trail. Admin
roles only. The ``AuditLog`` model and write path live in the kernel
(``studioerp.audit``); this router only exposes the read/export surface.
"""

from collections import Counter
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.db.session import get_db
from studioerp.platform.deps import require_min_level
from studioerp.platform.users import User
from studioerp.rings.comms.audit import service
from studioerp.rings.comms.audit.schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
) -> list[dict]:
    rows = await service.fetch_audit_logs(
        db,
        user_id=user_id,
        entity_type=entity_type,
        action=action,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_name": user_name,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "user_agent": log.user_agent,
            "created_at": log.created_at,
        }
        for log, user_name in rows
    ]


@router.get("/count")
async def audit_log_count(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = None,
) -> dict:
    total = await service.count_audit_logs(db, entity_type=entity_type)
    return {"total": total}


@router.get("/export")
async def export_audit_logs(
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    entity_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
) -> Response:
    rows = await service.fetch_export_rows(
        db,
        entity_type=entity_type,
        from_date=from_date,
        to_date=to_date,
    )

    action_counts = Counter(log.action for log, _ in rows)
    entity_counts = Counter(log.entity_type for log, _ in rows)

    if format == "xlsx":
        content = service._build_audit_xlsx(rows, action_counts, entity_counts)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="audit_logs.xlsx"'},
        )

    content = service._build_audit_csv(rows, action_counts, entity_counts)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_logs.csv"},
    )
