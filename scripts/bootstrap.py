"""Idempotent DB bootstrap for the studioerp-v2 Docker dev stack.

v2 does not ship alembic migrations yet (fresh-baseline decision), so the
container creates the schema from metadata and seeds a minimal baseline:
departments, org levels (L0-L6) and the first superuser. Safe to re-run.

Usage:  python -m scripts.bootstrap
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select

# Import every ring model so Base.metadata knows all tables and the ORM mapper
# configuration resolves (platform Department/OrgLevel must load first).
import studioerp.audit  # noqa: F401  (kernel AuditLog -- login/audit write path)
import studioerp.platform.notifications.models  # noqa: F401
import studioerp.platform.orgstructure.models  # noqa: F401
import studioerp.platform.settings.models  # noqa: F401
import studioerp.platform.users  # noqa: F401
import studioerp.rings.comms.backup.models  # noqa: F401
import studioerp.rings.comms.meetings.models  # noqa: F401
import studioerp.rings.comms.notices.models  # noqa: F401
import studioerp.rings.money.clients.models  # noqa: F401
import studioerp.rings.money.finance.models  # noqa: F401
import studioerp.rings.money.payroll.models  # noqa: F401
import studioerp.rings.people.attendance.models  # noqa: F401
import studioerp.rings.people.employees.models  # noqa: F401
import studioerp.rings.people.holidays.models  # noqa: F401
import studioerp.rings.people.leave.models  # noqa: F401
import studioerp.rings.work.projects.models  # noqa: F401
import studioerp.rings.work.site_visits.models  # noqa: F401
import studioerp.rings.work.tasks.models  # noqa: F401
import studioerp.rings.work.timesheets.models  # noqa: F401

from studioerp.config import settings
from studioerp.db.base import Base
from studioerp.db.session import get_engine, get_session_factory
from studioerp.platform.orgstructure.models import Department, OrgLevel
from studioerp.platform.settings.models import Setting
from studioerp.platform.users import User
from studioerp.rings.people.identity.repository import user_repository
from studioerp.security import format_login_id, hash_password
from studioerp.time import now_local

DEPARTMENTS = [
    {"name": "Administration", "description": "Core administration and office management"},
    {"name": "Architecture", "description": "Architectural design and planning"},
    {"name": "Interior Design", "description": "Interior design and fit-out"},
    {"name": "Urban Planning", "description": "Urban and landscape planning"},
    {"name": "Engineering", "description": "Structural and MEP engineering"},
    {"name": "Projects", "description": "Project delivery and site management"},
    {"name": "Finance", "description": "Finance, accounts and billing"},
    {"name": "Human Resources", "description": "People operations and recruitment"},
]

ORG_LEVELS = [
    {"code": "L0", "name": "Chief Executive Officer", "description": "CEO / owner", "rank": 0},
    {"code": "L1", "name": "Executive", "description": "Director / executive", "rank": 1},
    {"code": "L2", "name": "Leadership", "description": "Department head", "rank": 2},
    {"code": "L3", "name": "Management", "description": "Project / team lead", "rank": 3},
    {"code": "L4", "name": "Senior Professional", "description": "Senior individual contributor", "rank": 4},
    {"code": "L5", "name": "Professional", "description": "Individual contributor", "rank": 5},
    {"code": "L6", "name": "Junior / Entry", "description": "Junior / intern", "rank": 6},
]

COMPANY_SETTINGS = {
    "company": {
        "profile": {
            "name": "StudioERP",
            "tagline": "Architecture & Interiors",
            "monogram": "SE",
            "address": "42 Studio Lane, Bengaluru, Karnataka 560001",
            "phone": "+91 80 4123 4567",
            "email": "hello@studioerp.dev",
            "website": "https://studioerp.dev",
            "base_currency": "INR",
        }
    }
}


async def seed_departments(db) -> None:
    for dept in DEPARTMENTS:
        exists = await db.execute(select(Department).where(Department.name == dept["name"]))
        if exists.scalar_one_or_none():
            continue
        db.add(Department(**dept))
    await db.commit()


async def seed_org_levels(db) -> None:
    for level in ORG_LEVELS:
        exists = await db.execute(select(OrgLevel).where(OrgLevel.code == level["code"]))
        if exists.scalar_one_or_none():
            continue
        db.add(OrgLevel(**level))
    await db.commit()


async def seed_settings(db) -> None:
    for group, group_settings in COMPANY_SETTINGS.items():
        for key, value in group_settings.items():
            exists = await db.execute(
                select(Setting).where(Setting.group == group, Setting.key == key)
            )
            if exists.scalar_one_or_none():
                continue
            db.add(Setting(group=group, key=key, value=value))
    await db.commit()


async def seed_superuser(db) -> None:
    email = settings.first_superuser_email.lower()
    exists = await db.execute(select(User).where(User.email == email))
    if exists.scalar_one_or_none():
        return
    level = (
        await db.execute(select(OrgLevel).where(OrgLevel.code == "L0"))
    ).scalar_one_or_none()
    if level is None:
        level = (
            await db.execute(select(OrgLevel).where(OrgLevel.code == "L1"))
        ).scalar_one_or_none()
    year = now_local().date().year
    login_id = format_login_id(year, await user_repository.next_login_sequence(db, year))
    db.add(
        User(
            email=email,
            login_id=login_id,
            name="Studio Owner",
            org_level_id=level.id if level else None,
            designation="Chief Executive Officer",
            password_hash=hash_password(settings.first_superuser_password),
        )
    )
    await db.commit()
    print(f"  created superuser: {email} / login {login_id}")


async def main() -> None:
    print("studioerp-v2 bootstrap: creating schema…")
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  schema ready; seeding baseline…")

    db = get_session_factory()()
    try:
        await seed_org_levels(db)
        await seed_departments(db)
        await seed_settings(db)
        await seed_superuser(db)
    finally:
        await db.close()

    print("bootstrap complete.")


if __name__ == "__main__":
    asyncio.run(main())
