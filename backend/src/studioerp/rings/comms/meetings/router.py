"""Meeting scheduling and RSVP routes (ring r5/comms). Ported from
``app/modules/meetings/routes.py``.

Endpoints: /meetings — CRUD, RSVP responses. Management (L3+) can create;
only L2+ or the organizer can modify a meeting.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.enums import RsvpStatus
from studioerp.errors import MeetingError
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.users import User
from studioerp.rbac import has_min_level
from studioerp.rings.comms.meetings import service as meeting_service
from studioerp.rings.comms.meetings.models import Meeting
from studioerp.rings.comms.meetings.schemas import MeetingCreate, MeetingOut, MeetingUpdate
from studioerp.schemas import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/meetings", tags=["meetings"])


def _domain_error(exc: MeetingError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _get_or_404(db: AsyncSession, meeting_id: int) -> Meeting:
    meeting = await db.get(Meeting, meeting_id)
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return meeting


def _can_manage(meeting: Meeting, user: User) -> bool:
    return has_min_level(user, "L2") or meeting.organizer_id == user.id


@router.get("", response_model=PaginatedResponse[MeetingOut])
async def list_meetings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    include_all = has_min_level(current_user, "L3")
    items, total = await meeting_service.list_meetings(
        db, current_user, include_all, page, page_size
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=MeetingOut, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreate,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    try:
        result = await meeting_service.create_meeting(db, payload, current_user)
    except MeetingError as exc:
        raise _domain_error(exc) from exc
    await log_audit(
        db,
        current_user,
        "create",
        "meeting",
        entity_id=str(result["id"]),
        details={"title": result["title"]},
    )
    await db.commit()
    return result


@router.patch("/{meeting_id}", response_model=MeetingOut)
async def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    meeting = await _get_or_404(db, meeting_id)
    if not _can_manage(meeting, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")
    try:
        result = await meeting_service.update_meeting(db, meeting, payload, current_user)
    except MeetingError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "update", "meeting", entity_id=str(meeting_id))
    await db.commit()
    return result


@router.delete("/{meeting_id}", response_model=MessageResponse)
async def delete_meeting(
    meeting_id: int,
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    meeting = await _get_or_404(db, meeting_id)
    if not _can_manage(meeting, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the organizer")
    await log_audit(db, current_user, "delete", "meeting", entity_id=str(meeting_id))
    await meeting_service.delete_meeting(db, meeting)
    await db.commit()
    return MessageResponse(message="Meeting deleted")


@router.post("/{meeting_id}/rsvp", response_model=MeetingOut)
async def rsvp_meeting(
    meeting_id: int,
    rsvp_status: RsvpStatus,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    meeting = await _get_or_404(db, meeting_id)
    try:
        result = await meeting_service.rsvp(db, meeting, current_user, rsvp_status)
    except MeetingError as exc:
        raise _domain_error(exc) from exc
    await db.commit()
    return result
