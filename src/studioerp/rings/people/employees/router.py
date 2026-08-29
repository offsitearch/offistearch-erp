"""Employee management routes (r2/people). Ported from ``app/modules/employees/routes.py``.

Endpoints: /employees — directory, profiles, create/update, soft-delete, org
chart, designation catalogs, document records. Deferred to owning rings/phases:
purge (cross-ring), salary (money r4), attendance-summary & leaves (sibling
people modules) and storage-backed document upload/download.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studioerp.audit import log_audit
from studioerp.db.session import get_db
from studioerp.errors import EmployeeError
from studioerp.platform.deps import get_current_user, require_min_level
from studioerp.platform.orgstructure.models import OrgLevel
from studioerp.platform.users import User
from studioerp.rbac import has_min_level, level_rank, user_level_rank
from studioerp.rings.people.employees import service as employee_service
from studioerp.rings.people.employees.schemas import (
    DocumentOut,
    EmployeeCreate,
    EmployeeCreateOut,
    EmployeePage,
    EmployeeUpdate,
    OrgChartNode,
    ProfileOut,
)
from studioerp.schemas import PaginatedResponse

router = APIRouter(prefix="/employees", tags=["employees"])


@router.get("", response_model=EmployeePage)
async def list_employees(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
    search: str | None = Query(default=None, max_length=100),
    department_id: int | None = None,
    org_level_id: int | None = None,
    skill: str | None = Query(default=None, max_length=50),
    active_only: bool = True,
    inactive_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> EmployeePage:
    items, total = await employee_service.list_employees(
        db,
        search,
        department_id,
        skill,
        active_only,
        inactive_only,
        page,
        page_size,
        org_level_id=org_level_id,
    )
    return EmployeePage(items=items, total=total, page=page, page_size=page_size)


@router.get("/skills", response_model=list[str])
async def list_skills(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[str]:
    return await employee_service.list_skills(db)


@router.get("/designations", response_model=dict[str, list[str]])
async def designation_catalog(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
) -> dict[str, list[str]]:
    """Suggested designations per organizational level. HR info only."""
    return await employee_service.get_designation_catalog()


@router.get("/department-designations", response_model=dict[str, list[str]])
async def department_designation_catalog(
    current_user: Annotated[User, Depends(require_min_level("L3"))],
) -> dict[str, list[str]]:
    """Suggested designations per department name. HR info only."""
    return await employee_service.get_department_designation_catalog()


@router.get("/org-chart", response_model=list[OrgChartNode])
async def org_chart(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict]:
    return await employee_service.org_chart(db)


@router.post("", response_model=EmployeeCreateOut, status_code=status.HTTP_201_CREATED)
async def create_employee(
    payload: EmployeeCreate,
    current_user: Annotated[User, Depends(require_min_level("L2"))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeCreateOut:
    if payload.org_level_id is not None:
        level = await db.get(OrgLevel, payload.org_level_id)
        target_code = level.code if level else None
        # Strictly junior only — never the creator's own level or above.
        if level_rank(target_code) <= user_level_rank(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only assign organizational levels below your own",
            )
    try:
        user, password = await employee_service.create_employee(db, payload)
    except EmployeeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "create", "employee", entity_id=str(user.id))
    await db.commit()
    profile = await employee_service.get_profile(db, user.id)
    return EmployeeCreateOut(**profile, generated_password=password)


@router.get("/{user_id}", response_model=ProfileOut)
async def get_employee(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    if not has_min_level(current_user, "L3") and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    try:
        return await employee_service.get_profile(db, user_id)
    except EmployeeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{user_id}", response_model=ProfileOut)
async def update_employee(
    user_id: int,
    payload: EmployeeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileOut:
    is_management = has_min_level(current_user, "L3")
    if not (is_management or current_user.id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    target = (
        await db.execute(
            select(User).options(selectinload(User.org_level)).where(User.id == user_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # Rank-based administration hardening: nobody admin-edits a senior
    # colleague (self-edit stays allowed via the identity check above).
    if target.id != current_user.id and user_level_rank(target) < user_level_rank(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot edit a user senior to your organizational level",
        )
    if "is_active" in payload.model_dump(exclude_unset=True) and not has_min_level(
        current_user, "L1"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Executive Leadership can activate or deactivate an employee",
        )
    if payload.org_level_id is not None:
        level = await db.get(OrgLevel, payload.org_level_id)
        if level is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organizational level not found",
            )
        target_code = level.code
        if target_code == "L1" and not has_min_level(current_user, "L1"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only Executive Leadership can assign L1",
            )
        if level_rank(target_code) < user_level_rank(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You cannot assign an organizational level senior to your own",
            )
    try:
        updated = await employee_service.update_employee(
            db, target, payload, current_user, allow_full=is_management
        )
    except EmployeeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    await log_audit(db, current_user, "update", "employee", entity_id=str(user_id))
    await db.commit()
    return ProfileOut.model_validate(await employee_service.get_profile(db, updated.id))


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    user_id: int,
    current_user: Annotated[User, Depends(require_min_level("L1"))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    target = (
        await db.execute(
            select(User).options(selectinload(User.org_level)).where(User.id == user_id)
        )
    ).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )
    if user_level_rank(target) < user_level_rank(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot deactivate a user senior to your organizational level",
        )
    await employee_service.soft_delete(db, target)
    await log_audit(db, current_user, "delete", "employee", entity_id=str(user_id))
    await db.commit()


@router.get("/{user_id}/documents", response_model=PaginatedResponse[DocumentOut])
async def list_documents(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict:
    if not has_min_level(current_user, "L3") and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )
    items, total = await employee_service.list_documents(db, user_id, page, page_size)
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)
