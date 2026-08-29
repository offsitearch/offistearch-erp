"""Org-level authorization & financial-isolation policy (kernel k0).

Authorization is driven by the user's organizational level (L0-L6). Ranks are
canonical and hardcoded here so that runtime edits to ``org_levels.rank`` (a
display-ordering field) can never silently change permissions. L0 is the most
senior.

Financial data (invoices, expenses, payroll, salary, budgets, fees, deal
values, revenue figures) is restricted to L0 CEO and L1 Director by explicit
client mandate. ``FINANCIAL_LEVEL`` is the single source of truth: designation
and department never grant access.

The kernel defines the *policy* as pure functions over a lightweight
``RbacPrincipal`` (a user-like object exposing ``org_level``, whose ``.code``
is the org-level code). FastAPI dependencies in ``studioerp.api`` wire this to
the current request.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from typing import Any

LEVEL_RANK: dict[str, int] = {
    "L0": 0,  # CEO
    "L1": 1,  # Executive (Director)
    "L2": 2,  # Leadership (Department Head)
    "L3": 3,  # Management (Project / Team Lead)
    "L4": 4,  # Senior Professional
    "L5": 5,  # Professional
    "L6": 6,  # Junior / Entry (incl. interns)
}

UNKNOWN_LEVEL_RANK = 99  # users without a level are least-privileged

ExecutiveLevels = ("L0", "L1")
LeadershipLevels = ("L0", "L1", "L2")
ManagementLevels = ("L0", "L1", "L2", "L3")

# Financial boundary — client mandate: L0 CEO / L1 Director only.
FINANCIAL_LEVEL = "L1"

STAFF_MIN_RANK = LEVEL_RANK["L4"]  # rank >= this => self-service band


class RbacPrincipal(Protocol):
    """Minimal user-like shape the RBAC policy reads.

    Rings provide a concrete model that satisfies this protocol (an
    ``org_level`` object exposing ``.code``).
    """

    @property
    def org_level(self) -> "Any | None": ...


def level_rank(code: str | None) -> int:
    """Canonical authorization rank for a level code (lower = seniorer)."""
    if not code:
        return UNKNOWN_LEVEL_RANK
    return LEVEL_RANK.get(code, UNKNOWN_LEVEL_RANK)


def user_level_code(user: RbacPrincipal) -> str | None:
    return user.org_level.code if user.org_level else None


def user_level_rank(user: RbacPrincipal) -> int:
    return level_rank(user_level_code(user))


def has_min_level(user: RbacPrincipal, min_level: str) -> bool:
    """True when the user's level is ``min_level`` or more senior."""
    return user_level_rank(user) <= LEVEL_RANK[min_level]


def has_financial_access(user: RbacPrincipal) -> bool:
    """True only for the financial-data boundary (L0 CEO / L1 Director).

    In-process counterpart of the ``require_financial_access`` dependency —
    use it when serializing responses so financial fields can be omitted
    rather than nulled for unauthorized callers.
    """
    return has_min_level(user, FINANCIAL_LEVEL)


def is_staff_band(user: RbacPrincipal) -> bool:
    """True for the self-service band (L4-L6 or unknown): scoped to own data."""
    return user_level_rank(user) >= STAFF_MIN_RANK
