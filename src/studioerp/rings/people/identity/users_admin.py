"""User-admin schemas (r2).

Ported from ``app/modules/identity/users_admin.py``; definitions live in
``schemas.py``, re-exported here to preserve the reference module's public
boundary.
"""

from studioerp.rings.people.identity.schemas import (
    UserAdminCreateOut,
    UserAdminOut,
    UserBriefOut,
    UserCreateIn,
    UserUpdateIn,
)

__all__ = ["UserAdminCreateOut", "UserAdminOut", "UserBriefOut", "UserCreateIn", "UserUpdateIn"]
