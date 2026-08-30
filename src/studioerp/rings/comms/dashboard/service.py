"""Dashboard summary aggregation (ring r4/comms).

Ported from ``app/modules/dashboard/routes.py``. Pure cross-domain read
aggregator — owns no tables; counts are read concurrently across the people,
work and money rings.
"""

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.enums import InvoiceStatus, ProjectStatus, TaskStatus
from studioerp.platform.users import User
from studioerp.rbac import has_financial_access, is_staff_band
from studioerp.rings.money.finance.models import Invoice
from studioerp.rings.people.attendance.models import Attendance
from studioerp.rings.work.projects import service as project_service
from studioerp.rings.work.projects.models import Project
from studioerp.rings.work.tasks.models import Task
from studioerp.time import now_local

_ACTIVE_PROJECT_STATUSES = (
    ProjectStatus.DRAFT,
    ProjectStatus.CONCEPT,
    ProjectStatus.DESIGN,
    ProjectStatus.UNDER_REVIEW,
    ProjectStatus.IN_CONSTRUCTION,
)
_OPEN_TASK_STATUSES = (
    TaskStatus.TODO,
    TaskStatus.IN_PROGRESS,
    TaskStatus.REVIEW,
    TaskStatus.BLOCKED,
)


async def get_summary(db: AsyncSession, user: User) -> dict:
    staff_filter = [User.is_active.is_(True)]

    scope_user_id = user.id if is_staff_band(user) else None

    present_today_task = db.scalar(
        select(func.count())
        .select_from(Attendance)
        .join(User, User.id == Attendance.user_id)
        .where(
            *staff_filter,
            Attendance.date == now_local().date(),
            Attendance.check_in_time.isnot(None),
        )
    )

    active_projects_stmt = select(func.count(Project.id)).where(
        Project.is_active.is_(True),
        Project.status.in_(_ACTIVE_PROJECT_STATUSES),
    )
    if scope_user_id is not None:
        active_projects_stmt = active_projects_stmt.where(
            project_service.scope_condition(scope_user_id)
        )
    active_projects_task = db.scalar(active_projects_stmt)

    pending_tasks_stmt = select(func.count(Task.id)).where(
        Task.is_active.is_(True),
        Task.status.in_(_OPEN_TASK_STATUSES),
    )
    if scope_user_id is not None:
        pending_tasks_stmt = pending_tasks_stmt.where(Task.assigned_to == scope_user_id)
    pending_tasks_task = db.scalar(pending_tasks_stmt)

    tasks = [present_today_task, active_projects_task, pending_tasks_task]

    revenue_task = None
    if has_financial_access(user):
        month_start = now_local().date().replace(day=1)
        revenue_task = db.scalar(
            select(func.coalesce(func.sum(Invoice.paid_amount), 0)).where(
                Invoice.invoice_date >= month_start,
                Invoice.status != InvoiceStatus.CANCELLED,
            )
        )
        tasks.append(revenue_task)

    total_employees = await db.scalar(select(func.count()).select_from(User).where(*staff_filter))
    results = await asyncio.gather(*tasks)

    present_today = results[0]
    active_projects = results[1]
    pending_tasks = results[2]
    revenue_this_month = results[3] if revenue_task is not None else None

    return {
        "total_employees": total_employees or 0,
        "present_today": present_today or 0,
        "active_projects": active_projects or 0,
        "revenue_this_month": revenue_this_month,
        "pending_tasks": pending_tasks or 0,
    }