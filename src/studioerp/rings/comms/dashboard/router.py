"""Dashboard aggregation routes (ring r4/comms). Ported from
``app/modules/dashboard/routes.py``.

Endpoint: /dashboard/summary — org-wide stats. Any authenticated user; staff-band
users see scoped counts and financial figures are omitted for non-executives.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.db.session import get_db
from studioerp.platform.deps import get_current_user
from studioerp.platform.users import User
from studioerp.rings.comms.dashboard import service as dashboard_service
from studioerp.rings.comms.dashboard.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    return await dashboard_service.get_summary(db, current_user)