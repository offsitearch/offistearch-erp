"""Backup & restore routes.

Endpoints: /backup — status, Google Drive one-click OAuth connect,
manual/scheduled backups, history and a direct JSON-dump download.
The whole router is executive-only (L0/L1) — backups contain every
table in the database including salary and financial data.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.config import settings
from studioerp.db.session import get_db
from studioerp.platform.deps import require_min_level
from studioerp.platform.users import User
from studioerp.rings.comms.backup import service as backup_service
from studioerp.rings.comms.backup.models import BackupHistory
from studioerp.rings.comms.backup.schemas import (
    BackupHistoryOut,
    BackupScheduleIn,
    BackupStatusOut,
)
from studioerp.schemas import MessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backup", tags=["backup"])


@router.get("/status", response_model=BackupStatusOut)
async def backup_status(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    return await backup_service.status_payload(db)


@router.get("/history", response_model=list[BackupHistoryOut])
async def backup_history(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[BackupHistory]:
    return await backup_service.list_history(db, limit)


@router.get("/google/connect")
async def google_connect(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
) -> RedirectResponse:
    """One-click setup: bounce the browser through Google's consent screen.

    The callback stores the tokens and redirects back to the settings page.
    """
    return backup_service.connect_redirect()


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    # `state` must carry a fresh HMAC signature from our own connect
    # endpoint — otherwise this route would accept authorization codes from
    # anywhere (OAuth CSRF → attacker-hosted Drive receiving backups).
    if error or not code or not backup_service.verify_state(state):
        if not error:
            logger.warning("Google Drive callback rejected (bad or missing state)")
        return RedirectResponse(url=f"{settings.backup_ui_redirect}&drive=error")
    from studioerp.db.session import get_session_factory

    async with get_session_factory()() as db:
        try:
            await backup_service.exchange_code(db, code)
            await db.commit()
        except Exception:  # noqa: BLE001 — user-facing redirect carries the state
            logger.exception("Google Drive token exchange failed")
            return RedirectResponse(url=f"{settings.backup_ui_redirect}&drive=error")
    return RedirectResponse(url=f"{settings.backup_ui_redirect}&drive=connected")


@router.post("/google/disconnect", response_model=MessageResponse)
async def google_disconnect(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    await backup_service.disconnect(db)
    await log_audit(db, current_user, "delete", "backup_google_connection")
    await db.commit()
    return MessageResponse(message="Google Drive disconnected")


@router.put("/schedule", response_model=BackupStatusOut)
async def update_schedule(
    payload: BackupScheduleIn,
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    status = await backup_service.update_schedule(db, payload.auto_enabled, payload.frequency)
    await log_audit(
        db,
        current_user,
        "update",
        "backup_schedule",
        details={"auto_enabled": payload.auto_enabled, "frequency": payload.frequency},
    )
    await db.commit()
    return status


@router.post("/run", response_model=BackupHistoryOut)
async def run_backup(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BackupHistory:
    history = await backup_service.run_backup(db, trigger="manual")
    if history.status != "success":
        raise HTTPException(status_code=502, detail=f"Backup failed: {history.error_message}")
    await log_audit(
        db,
        current_user,
        "create",
        "backup",
        details={"file_name": history.file_name, "size_bytes": history.file_size_bytes},
    )
    # run_backup already committed; audit trail rides the same session state
    await db.commit()
    return history


@router.get("/download")
async def download_backup(
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamingResponse:
    """Direct one-click download of a fresh database dump (no Drive needed)."""
    content, file_name = await backup_service.build_dump(db)
    await log_audit(db, current_user, "create", "backup_download", details={"file_name": file_name})
    await db.commit()
    return StreamingResponse(
        iter([content]),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.post("/restore")
async def restore_backup(
    current_user: Annotated[User, Depends(require_min_level("L0"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: Annotated[UploadFile, File()],
) -> dict:
    """Upload a ``.json.gz`` dump and restore the database from it.

    Destructive: all tables present in the archive are replaced. Executive-only
    (L0) because this overwrites every table in the database.
    """
    from studioerp.upload import ALLOWED_BACKUP_EXTENSIONS, validate_upload

    content = await file.read()
    validate_upload(file, content, allowed=ALLOWED_BACKUP_EXTENSIONS, label="backup")
    try:
        result = await backup_service.restore_dump(db, content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await log_audit(
        db,
        current_user,
        "restore",
        "backup",
        details=result,
    )
    await db.commit()
    return result