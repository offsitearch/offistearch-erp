"""Dashboard summary schemas (ring r4/comms). Ported from
``app/modules/dashboard/routes.py``.
"""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_employees: int
    present_today: int
    active_projects: int
    pending_tasks: int
    revenue_this_month: Decimal | None = None