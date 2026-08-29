"""Site visit CRUD (ring r3/work). Ported from ``app/modules/site_visits/service.py``.

Deferred until the storage/PDF abstractions land: photo upload/download and the
site-visit PDF report. Photo columns are still exposed (always empty for now).
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.errors import SiteVisitError
from studioerp.platform.users import User
from studioerp.rings.work.projects.models import Project
from studioerp.rings.work.site_visits.models import SiteVisit, SiteVisitPhoto
from studioerp.rings.work.site_visits.schemas import SiteVisitCreate, SiteVisitUpdate
from studioerp.state_machines import assert_transition
from studioerp.time import utc_now


async def _profile(db: AsyncSession, visit: SiteVisit) -> dict:
    project = await db.get(Project, visit.project_id) if visit.project_id else None
    creator = await db.get(User, visit.created_by) if visit.created_by else None
    photo_rows = (
        (
            await db.execute(
                select(SiteVisitPhoto)
                .where(SiteVisitPhoto.site_visit_id == visit.id)
                .order_by(SiteVisitPhoto.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": visit.id,
        "project_id": visit.project_id,
        "project_code": project.project_code if project else None,
        "project_name": project.name if project else None,
        "visit_date": visit.visit_date,
        "start_time": visit.start_time,
        "end_time": visit.end_time,
        "status": visit.status.value,
        "purpose": visit.purpose,
        "notes": visit.notes,
        "location": visit.location,
        "weather": visit.weather,
        "attendance_notes": visit.attendance_notes,
        "created_by": visit.created_by,
        "creator_name": creator.name if creator else None,
        "completed_at": visit.completed_at,
        "photos": [
            {
                "id": photo.id,
                "file_path": photo.file_path,
                "caption": photo.caption,
                "uploaded_by": photo.uploaded_by,
                "uploaded_at": photo.uploaded_at,
            }
            for photo in photo_rows
        ],
    }


async def list_visits(
    db: AsyncSession,
    include_all: bool = False,
    current_user_id: int | None = None,
    project_id: int | None = None,
    status: str | None = None,
    scope_project_ids: list[int] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[dict], int]:
    stmt = select(SiteVisit).order_by(SiteVisit.visit_date.desc(), SiteVisit.id.desc())
    if not include_all:
        if scope_project_ids:
            stmt = stmt.where(
                or_(
                    SiteVisit.created_by == current_user_id,
                    SiteVisit.project_id.in_(scope_project_ids),
                )
            )
        else:
            stmt = stmt.where(SiteVisit.created_by == current_user_id)
    if project_id is not None:
        stmt = stmt.where(SiteVisit.project_id == project_id)
    if status:
        stmt = stmt.where(SiteVisit.status == status)
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()
    visits = (
        (await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    )
    if not visits:
        return [], total
    visit_ids = [visit.id for visit in visits]
    photos_by_visit: dict[int, list[SiteVisitPhoto]] = {}
    photo_rows = (
        (
            await db.execute(
                select(SiteVisitPhoto)
                .where(SiteVisitPhoto.site_visit_id.in_(visit_ids))
                .order_by(SiteVisitPhoto.id)
            )
        )
        .scalars()
        .all()
    )
    for photo in photo_rows:
        photos_by_visit.setdefault(photo.site_visit_id, []).append(photo)

    project_ids = {v.project_id for v in visits if v.project_id is not None}
    projects: dict[int, Project] = {}
    if project_ids:
        projects = {
            p.id: p
            for p in (await db.execute(select(Project).where(Project.id.in_(project_ids))))
            .scalars()
            .all()
        }
    creator_ids = {v.created_by for v in visits if v.created_by is not None}
    creators: dict[int, User] = {}
    if creator_ids:
        creators = {
            u.id: u
            for u in (await db.execute(select(User).where(User.id.in_(creator_ids))))
            .scalars()
            .all()
        }

    items = [
        {
            "id": visit.id,
            "project_id": visit.project_id,
            "project_code": projects[visit.project_id].project_code
            if visit.project_id in projects
            else None,
            "project_name": projects[visit.project_id].name
            if visit.project_id in projects
            else None,
            "visit_date": visit.visit_date,
            "start_time": visit.start_time,
            "end_time": visit.end_time,
            "status": visit.status.value,
            "purpose": visit.purpose,
            "notes": visit.notes,
            "location": visit.location,
            "weather": visit.weather,
            "attendance_notes": visit.attendance_notes,
            "created_by": visit.created_by,
            "creator_name": creators[visit.created_by].name
            if visit.created_by in creators
            else None,
            "completed_at": visit.completed_at,
            "photos": [
                {
                    "id": photo.id,
                    "file_path": photo.file_path,
                    "caption": photo.caption,
                    "uploaded_by": photo.uploaded_by,
                    "uploaded_at": photo.uploaded_at,
                }
                for photo in photos_by_visit.get(visit.id, [])
            ],
        }
        for visit in visits
    ]
    return items, total


async def create_visit(db: AsyncSession, payload: SiteVisitCreate, user: User) -> dict:
    project = await db.get(Project, payload.project_id)
    if project is None:
        raise SiteVisitError("Project not found", 404)
    visit = SiteVisit(
        project_id=payload.project_id,
        visit_date=payload.visit_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=payload.status,
        purpose=payload.purpose,
        notes=payload.notes,
        location=payload.location,
        weather=payload.weather,
        attendance_notes=payload.attendance_notes,
        created_by=user.id,
    )
    db.add(visit)
    await db.commit()
    await db.refresh(visit)
    return await _profile(db, visit)


async def update_visit(db: AsyncSession, visit: SiteVisit, payload: SiteVisitUpdate) -> dict:
    if payload.project_id is not None:
        project = await db.get(Project, payload.project_id)
        if project is None:
            raise SiteVisitError("Project not found", 404)
        visit.project_id = payload.project_id
    if payload.visit_date is not None:
        visit.visit_date = payload.visit_date
    if payload.start_time is not None:
        visit.start_time = payload.start_time
    if payload.end_time is not None:
        visit.end_time = payload.end_time
    if payload.status is not None:
        assert_transition(visit.status, payload.status, "site_visit")
        visit.status = payload.status
    if payload.purpose is not None:
        visit.purpose = payload.purpose
    if payload.notes is not None:
        visit.notes = payload.notes
    if payload.location is not None:
        visit.location = payload.location
    if payload.weather is not None:
        visit.weather = payload.weather
    if payload.attendance_notes is not None:
        visit.attendance_notes = payload.attendance_notes
    if payload.status is not None and payload.status.value == "completed":
        visit.completed_at = utc_now()
    await db.commit()
    await db.refresh(visit)
    return await _profile(db, visit)


async def delete_visit(db: AsyncSession, visit: SiteVisit) -> None:
    await db.delete(visit)
    await db.commit()
