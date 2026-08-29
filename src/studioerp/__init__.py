"""StudioERP kernel + rings.

The ``studioerp`` package root hosts the **kernel (k0)** — cross-cutting
primitives that depend on nothing internal (config, security, db, money,
rbac, errors, state machines, audit, exporters). Feature rings live in
``studioerp.rings.*`` and the API composition root in ``studioerp.api``.
"""

from studioerp.money import q
from studioerp.rbac import (
    FINANCIAL_LEVEL,
    LEVEL_RANK,
    UNKNOWN_LEVEL_RANK,
    has_financial_access,
    has_min_level,
    is_staff_band,
    user_level_rank,
)

__all__ = [
    "q",
    "FINANCIAL_LEVEL",
    "LEVEL_RANK",
    "UNKNOWN_LEVEL_RANK",
    "has_financial_access",
    "has_min_level",
    "is_staff_band",
    "user_level_rank",
]
