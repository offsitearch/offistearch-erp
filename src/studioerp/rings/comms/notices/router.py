"""Company notice/announcement routes (ring r5/comms). Ported from
``app/modules/notices/routes.py``.

Endpoints: /notices — CRUD for notices. Read for all authenticated users;
create/update/delete require Admin (L2+) roles.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.users import User
from studioerp.rbac import has_min_level
from studioerp.rings.comms.notices import service as notice_service
from studioerp.rings.comms.notices.models import Notice
from studioerp.rings.comms.notices.schemas import NoticeCreate, NoticeOut, NoticeUpdate
from studioerp.schemas import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/notices", tags=["notices"])


async def _get_or_404(db: AsyncSession, notice_id: int) -> Notice:
    notice = await db.get(Notice, notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found")
    return notice


@router.get("", response_model=PaginatedResponse[NoticeOut])
async def list_notices(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    include_inactive: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    is_admin = has_min_level(current_user, "L2")
    items, total = await notice_service.list_notices(
        db,
        include_inactive=include_inactive and is_admin,
        only_active_now=not is_admin,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=NoticeOut, status_code=status.HTTP_201_CREATED)
async def create_notice(
    payload: NoticeCreate,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    result = await notice_service.create_notice(db, payload, current_user)
    await log_audit(
        db,
        current_user,
        "create",
        "notice",
        entity_id=str(result["id"]),
        details={"title": result["title"]},
    )
    await db.commit()
    return result


@router.patch("/{notice_id}", response_model=NoticeOut)
async def update_notice(
    notice_id: int,
    payload: NoticeUpdate,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    notice = await _get_or_404(db, notice_id)
    result = await notice_service.update_notice(db, notice, payload)
    await log_audit(db, current_user, "update", "notice", entity_id=str(notice_id))
    await db.commit()
    return result


@router.delete("/{notice_id}", response_model=MessageResponse)
async def delete_notice(
    notice_id: int,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    notice = await _get_or_404(db, notice_id)
    await notice_service.soft_delete(db, notice)
    await log_audit(db, current_user, "delete", "notice", entity_id=str(notice_id))
    await db.commit()
    return MessageResponse(message="Notice deleted")