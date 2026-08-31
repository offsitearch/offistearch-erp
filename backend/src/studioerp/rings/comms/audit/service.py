"""Audit log read/export service (ring comms/audit).

Holds the query-building and export-builder helpers for the admin read surface.
The ``AuditLog`` model and the ``log_audit`` writer live in the kernel
(``studioerp.audit``); this module only reads and exports.
"""

import csv
import io
from collections import Counter
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import AuditLog
from studioerp.platform.users import User
from studioerp.xlsx import write_xlsx


def _export_columns(with_headers: bool = False) -> list[str]:
    return ["ID", "User", "Action", "Entity Type", "Entity ID", "IP Address", "Timestamp"]


def _detail_row(log, user_name) -> list:
    return [
        log.id,
        user_name or "",
        log.action,
        log.entity_type,
        log.entity_id or "",
        log.ip_address or "",
        log.created_at.isoformat() if log.created_at else "",
    ]


def _build_audit_xlsx(rows: list, action_counts: Counter, entity_counts: Counter) -> bytes:
    num_cols = 5
    extra_before: list[list[tuple[str, str | None]]] = [
        [("Audit Log Export", "title")] + [("", None)] * (num_cols - 1),
        [(f"Total Entries: {len(rows)}", "subtitle")] + [("", None)] * (num_cols - 1),
        [("", None)] * num_cols,
        [("Activity Summary", "section")] + [("", None)] * (num_cols - 1),
    ]
    for action, count in action_counts.most_common(10):
        extra_before.append([(action, "summary_label"), (str(count), "summary_value")] + [("", None)] * (num_cols - 2))
    if entity_counts:
        extra_before.append([("", None)] * num_cols)
        extra_before.append([("Entity Breakdown", "section")] + [("", None)] * (num_cols - 1))
        for entity, count in entity_counts.most_common(10):
            extra_before.append([(entity, "summary_label"), (str(count), "summary_value")] + [("", None)] * (num_cols - 2))

    columns = _export_columns()
    col_styles = ["integer_border", "text_border", "text_border", "text_border", "text_border", "text_border", "text_border"]
    alt_col_styles = ["integer_alt", "text_alt", "text_alt", "text_alt", "text_alt", "text_alt", "text_alt"]

    detail_rows = [_detail_row(log, user_name) for log, user_name in rows]

    return write_xlsx([{
        "name": "Audit Log",
        "columns": columns,
        "rows": detail_rows,
        "col_styles": col_styles,
        "alt_col_styles": alt_col_styles,
        "freeze_row": len(extra_before) + 1,
        "extra_rows_before": extra_before,
    }])


def _build_audit_csv(rows: list, action_counts: Counter, entity_counts: Counter) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Audit Log Export"])
    writer.writerow([f"Total Entries: {len(rows)}"])
    writer.writerow([])
    writer.writerow(["Action Breakdown"])
    for action, count in action_counts.most_common():
        writer.writerow([action, count])
    if entity_counts:
        writer.writerow([])
        writer.writerow(["Entity Breakdown"])
        for entity, count in entity_counts.most_common():
            writer.writerow([entity, count])
    writer.writerow([])
    writer.writerow([])
    writer.writerow(_export_columns())
    for log, user_name in rows:
        writer.writerow(_detail_row(log, user_name))
    return buf.getvalue()


async def fetch_audit_logs(
    db: AsyncSession,
    *,
    user_id: int | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list:
    stmt = (
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
    )
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if from_date:
        stmt = stmt.where(AuditLog.created_at >= from_date)
    if to_date:
        stmt = stmt.where(AuditLog.created_at <= to_date)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return (await db.execute(stmt)).all()


async def count_audit_logs(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
) -> int:
    stmt = select(func.count(AuditLog.id))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    return (await db.execute(stmt)).scalar() or 0


async def fetch_export_rows(
    db: AsyncSession,
    *,
    entity_type: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
) -> list:
    stmt = (
        select(AuditLog, User.name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(5000)
    )
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if from_date:
        stmt = stmt.where(AuditLog.created_at >= from_date)
    if to_date:
        stmt = stmt.where(AuditLog.created_at <= to_date)
    return (await db.execute(stmt)).all()
