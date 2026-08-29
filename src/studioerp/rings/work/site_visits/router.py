"""Site visit logging routes (ring r3/work). Ported from
``app/modules/site_visits/routes.py`` (CRUD subset).

Endpoints: /site-visits — list, create, get, update, delete. Authenticated
users; leaders see all visits, others see own + their projects'. Photo
upload/download and the PDF report are deferred until the storage/PDF
abstractions land.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import SiteVisitError
from studioerp.platform.deps import get_current_user
from studioerp.platform.users import User
from studioerp.rbac import (
    LEVEL_RANK,
    has_min_level,
    is_staff_band,
    user_level_rank,
)
from studioerp.rings.work.projects import service as project_service
from studioerp.rings.work.projects.models import Project
from studioerp.rings.work.site_visits import service as site_visit_service
from studioerp.rings.work.site_visits.models import SiteVisit
from studioerp.rings.work.site_visits.schemas import (
    SiteVisitCreate,
    SiteVisitOut,
    SiteVisitUpdate,
)
from studioerp.schemas import MessageResponse, PaginatedResponse

router = APIRouter(prefix="/site-visits", tags=["site-visits"])


def _domain_error(exc: SiteVisitError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


async def _get_or_404(db: AsyncSession, visit_id: int) -> SiteVisit:
    visit = await db.get(SiteVisit, visit_id)
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Site visit not found")
    return visit


async def _can_manage(db: AsyncSession, visit: SiteVisit, user: User) -> bool:
    if has_min_level(user, "L2") or visit.created_by == user.id:
        return True
    if has_min_level(user, "L3") and visit.project_id is not None:
        project = await db.get(Project, visit.project_id)
        return project is not None and project.project_lead_id == user.id
    return False


async def _can_view(db: AsyncSession, visit: SiteVisit, user: User) -> bool:
    if await _can_manage(db, visit, user):
        return True
    if is_staff_band(user) and visit.project_id is not None:
        return await project_service.user_in_project(db, visit.project_id, user.id)
    return False


@router.get("", response_model=PaginatedResponse[SiteVisitOut])
async def list_visits(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: int | None = None,
    status_: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse:
    scope_project_ids: list[int] | None = None
    if has_min_level(current_user, "L2"):
        include_all = True
    else:
        include_all = False
        led_rows = await db.execute(
            select(Project.id).where(Project.project_lead_id == current_user.id)
        )
        scope_project_ids = list(led_rows.scalars().all())
        if is_staff_band(current_user):
            member_ids = await project_service.user_project_ids(db, current_user.id)
            scope_project_ids = sorted(set(scope_project_ids) | set(member_ids))
    items, total = await site_visit_service.list_visits(
        db,
        include_all=include_all,
        current_user_id=current_user.id,
        project_id=project_id,
        status=status_,
        scope_project_ids=scope_project_ids,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)


@router.post(
    "", response_model=SiteVisitOut, status_code=status.HTTP_201_CREATED
)
async def create_visit(
    payload: SiteVisitCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if not has_min_level(current_user, "L2"):
        if user_level_rank(current_user) > LEVEL_RANK["L3"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        project = await db.get(Project, payload.project_id)
        if project is None or not project.is_active:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if project.project_lead_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the project lead can create visits for this project",
            )
    try:
        result = await site_visit_service.create_visit(db, payload, current_user)
    except SiteVisitError as exc:
        raise _domain_error(exc) from exc
    await log_audit(
        db,
        current_user,
        "create",
        "site_visit",
        entity_id=str(result["id"]),
        details={
            "project_id": result["project_id"],
            "visit_date": result["visit_date"].isoformat(),
        },
    )
    await db.commit()
    return result


@router.get("/{visit_id}", response_model=SiteVisitOut)
async def get_visit(
    visit_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    visit = await _get_or_404(db, visit_id)
    if not await _can_view(db, visit, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    return await site_visit_service._profile(db, visit)


@router.patch("/{visit_id}", response_model=SiteVisitOut)
async def update_visit(
    visit_id: int,
    payload: SiteVisitUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    visit = await _get_or_404(db, visit_id)
    if not await _can_manage(db, visit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the creator")
    try:
        result = await site_visit_service.update_visit(db, visit, payload)
    except SiteVisitError as exc:
        raise _domain_error(exc) from exc
    await log_audit(db, current_user, "update", "site_visit", entity_id=str(visit_id))
    await db.commit()
    return result


@router.delete("/{visit_id}", response_model=MessageResponse)
async def delete_visit(
    visit_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    visit = await _get_or_404(db, visit_id)
    if not await _can_manage(db, visit, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not the creator")
    await log_audit(db, current_user, "delete", "site_visit", entity_id=str(visit_id))
    await site_visit_service.delete_visit(db, visit)
    return MessageResponse(message="Site visit deleted")
