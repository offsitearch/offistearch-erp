"""Employee management service (r2/people). Ported from ``app/modules/employees/service.py``.

People-ring scope: directory, profiles, create/update, soft delete, org chart,
designation catalogs and document records. Salary, permanent purge (cross-ring)
and storage-backed document transfer are deferred to their owning rings.
"""

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from studioerp.errors import EmployeeError
from studioerp.platform.orgstructure.models import Department, OrgLevel
from studioerp.platform.org_structure import DEPARTMENT_DESIGNATIONS, DESIGNATION_CATALOG
from studioerp.platform.users import User
from studioerp.rings.people.employees.models import EmployeeDocument
from studioerp.rings.people.employees.schemas import EmployeeCreate, EmployeeUpdate
from studioerp.rings.people.identity.repository import user_repository
from studioerp.security import format_login_id, generate_email, generate_numeric_password, hash_password
from studioerp.time import now_local


async def list_employees(
    db: AsyncSession,
    search: str | None,
    department_id: int | None,
    skill: str | None,
    active_only: bool,
    inactive_only: bool,
    page: int,
    page_size: int,
    org_level_id: int | None = None,
) -> tuple[list[dict], int]:
    stmt = (
        select(User, Department.name, OrgLevel)
        .outerjoin(Department, Department.id == User.department_id)
        .outerjoin(OrgLevel, OrgLevel.id == User.org_level_id)
        .order_by(User.name)
    )
    count_stmt = select(func.count(User.id)).outerjoin(
        Department, Department.id == User.department_id
    )

    if search:
        like = f"%{search}%"
        cond = or_(
            User.name.ilike(like),
            User.email.ilike(like),
            User.employee_id.ilike(like),
            User.designation.ilike(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)
    if department_id is not None:
        stmt = stmt.where(User.department_id == department_id)
        count_stmt = count_stmt.where(User.department_id == department_id)
    if org_level_id is not None:
        stmt = stmt.where(User.org_level_id == org_level_id)
        count_stmt = count_stmt.where(User.org_level_id == org_level_id)
    if skill:
        stmt = stmt.where(User.skills.any(skill))
        count_stmt = count_stmt.where(User.skills.any(skill))
    if inactive_only:
        stmt = stmt.where(User.is_active.is_(False))
        count_stmt = count_stmt.where(User.is_active.is_(False))
    elif active_only:
        stmt = stmt.where(User.is_active.is_(True))
        count_stmt = count_stmt.where(User.is_active.is_(True))

    total = (await db.execute(count_stmt)).scalar_one()
    result = await db.execute(stmt.offset((page - 1) * page_size).limit(page_size))
    items = [
        {
            "id": user.id,
            "employee_id": user.employee_id,
            "name": user.name,
            "email": user.email,
            "contact_email": user.contact_email,
            "department": dept,
            "org_level_code": level.code if level else None,
            "org_level_name": level.name if level else None,
            "designation": user.designation,
            "employment_type": user.employment_type.value,
            "is_active": user.is_active,
        }
        for user, dept, level in result.all()
    ]
    return items, total


async def list_skills(db: AsyncSession) -> list[str]:
    rows = (await db.execute(select(User.skills).where(User.skills.is_not(None)))).all()
    skills: set[str] = set()
    for (row,) in rows:
        skills.update(row or [])
    return sorted(skills)


async def get_profile(db: AsyncSession, user_id: int) -> dict:
    stmt = (
        select(User, Department.name, OrgLevel)
        .outerjoin(Department, Department.id == User.department_id)
        .outerjoin(OrgLevel, OrgLevel.id == User.org_level_id)
        .where(User.id == user_id)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        raise EmployeeError("Employee not found", 404)
    user, dept_name, level = row
    return _profile_dict(user, dept_name, level)


def _profile_dict(user: User, dept_name: str | None, level: OrgLevel | None = None) -> dict:
    return {
        "id": user.id,
        "login_id": user.login_id,
        "employee_id": user.employee_id,
        "email": user.email,
        "contact_email": user.contact_email,
        "phone": user.phone,
        "name": user.name,
        "department_id": user.department_id,
        "department": dept_name,
        "org_level_id": level.id if level else None,
        "org_level_code": level.code if level else None,
        "org_level_name": level.name if level else None,
        "designation": user.designation,
        "reporting_to_id": user.reporting_to_id,
        "date_of_joining": user.date_of_joining,
        "date_of_birth": user.date_of_birth,
        "gender": user.gender,
        "blood_group": user.blood_group,
        "address": user.address,
        "emergency_contact_name": user.emergency_contact_name,
        "emergency_contact_phone": user.emergency_contact_phone,
        "skills": user.skills,
        "employment_type": user.employment_type.value,
        "is_active": user.is_active,
        "created_at": user.created_at,
    }


async def create_employee(db: AsyncSession, payload: EmployeeCreate) -> tuple[User, str]:
    joining_date = payload.date_of_joining
    email = generate_email(payload.name, joining_date)
    password = generate_numeric_password()

    existing = await user_repository.get_by_email(db, email)
    if existing:
        raise EmployeeError(
            "Generated email conflicts with existing user. Try a different name or joining date.",
            409,
        )

    if payload.employee_id:
        exists = (
            await db.execute(select(User).where(User.employee_id == payload.employee_id))
        ).scalar_one_or_none()
        if exists:
            raise EmployeeError("Employee ID already in use", 409)

    if payload.department_id is not None:
        dept = await db.get(Department, payload.department_id)
        if dept is None:
            raise EmployeeError("Department not found", 404)
    if payload.org_level_id is not None:
        level = await db.get(OrgLevel, payload.org_level_id)
        if level is None:
            raise EmployeeError("Organizational level not found", 404)
    if payload.reporting_to_id is not None:
        manager = await db.get(User, payload.reporting_to_id)
        if manager is None:
            raise EmployeeError("Reporting manager not found", 404)

    year = joining_date.year if joining_date else now_local().date().year
    for _ in range(5):
        sequence = await user_repository.next_login_sequence(db, year)
        login_id = format_login_id(year, sequence)
        taken = (
            await db.execute(select(User).where(User.login_id == login_id))
        ).scalar_one_or_none()
        if taken is None:
            break
    else:
        raise EmployeeError("Could not allocate a unique user ID for this joining year", 409)

    user = User(
        name=payload.name,
        login_id=login_id,
        email=email,
        contact_email=payload.contact_email,
        password_hash=hash_password(password),
        must_change_password=True,
        employee_id=payload.employee_id,
        phone=payload.phone,
        department_id=payload.department_id,
        org_level_id=payload.org_level_id,
        designation=payload.designation,
        reporting_to_id=payload.reporting_to_id,
        date_of_joining=payload.date_of_joining,
        date_of_birth=payload.date_of_birth,
        gender=payload.gender,
        employment_type=payload.employment_type,
        is_active=payload.is_active,
        skills=payload.skills,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user, password


async def update_employee(
    db: AsyncSession,
    target: User,
    payload: EmployeeUpdate,
    actor: User,
    allow_full: bool,
) -> User:
    data = payload.model_dump(exclude_unset=True)

    if not allow_full:
        allowed = {
            "phone",
            "contact_email",
            "emergency_contact_name",
            "emergency_contact_phone",
            "address",
            "skills",
        }
        data = {k: v for k, v in data.items() if k in allowed}

    if "employee_id" in data and data["employee_id"]:
        exists = (
            await db.execute(
                select(User).where(User.employee_id == data["employee_id"], User.id != target.id)
            )
        ).scalar_one_or_none()
        if exists:
            raise EmployeeError("Employee ID already in use", 409)
    if "org_level_id" in data and data["org_level_id"] is not None and target.id == actor.id:
        raise EmployeeError("You cannot change your own organizational level", 400)

    for field, value in data.items():
        if value is not None:
            setattr(target, field, value)

    await db.commit()
    await db.refresh(target)
    return target


async def soft_delete(db: AsyncSession, user: User) -> None:
    user.is_active = False
    await db.commit()


async def org_chart(db: AsyncSession) -> list[dict]:
    users = (
        (
            await db.execute(
                select(User)
                .options(selectinload(User.org_level), selectinload(User.department))
                .where(User.is_active == True)  # noqa: E712
                .order_by(User.name)
            )
        )
        .scalars()
        .all()
    )
    by_id = {
        u.id: {
            "user_id": u.id,
            "name": u.name,
            "employee_id": u.employee_id,
            "designation": u.designation,
            "department_id": u.department_id,
            "department_name": u.department.name if u.department else None,
            "org_level_code": u.org_level.code if u.org_level else None,
            "org_level_name": u.org_level.name if u.org_level else None,
            "reports_to_id": u.reporting_to_id,
            "children": [],
        }
        for u in users
    }
    roots: list[dict] = []
    for user in users:
        node = by_id[user.id]
        if user.reporting_to_id and user.reporting_to_id in by_id:
            by_id[user.reporting_to_id]["children"].append(node)
        else:
            roots.append(node)
    return roots


async def get_designation_catalog() -> dict[str, list[str]]:
    """Suggested designations per level code. HR information only."""
    return DESIGNATION_CATALOG


async def get_department_designation_catalog() -> dict[str, list[str]]:
    """Suggested designations per department name. HR information only."""
    return DEPARTMENT_DESIGNATIONS


async def list_documents(
    db: AsyncSession, user_id: int, page: int = 1, page_size: int = 20
) -> tuple[list[dict], int]:
    base = select(EmployeeDocument).where(EmployeeDocument.user_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(EmployeeDocument.uploaded_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    items = [
        {
            "id": doc.id,
            "user_id": doc.user_id,
            "doc_type": doc.doc_type,
            "file_name": doc.file_name,
            "uploaded_by": doc.uploaded_by,
            "uploaded_at": doc.uploaded_at,
        }
        for doc in rows
    ]
    return items, total
