"""API dependencies: current user + RBAC / financial-access guards.

Ported from the reference monolith ``app/api/deps.py``. Lives in the platform
ring (k1) because it is shared by every ring's routers; placing it here keeps
the inner ring from depending on the outer API composition root. The user-fetch
uses the platform ``get_user_by_id``.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.db.session import get_db
from studioerp.platform.users import User, get_user_by_id
from studioerp.rbac import FINANCIAL_LEVEL, LEVEL_RANK, user_level_rank
from studioerp.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

_PASSWORD_CHANGE_EXEMPT_PREFIXES = ("/api/v1/auth",)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(credentials.credentials)
    except PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if int(payload.get("tvp", -1)) != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalidated by a password change. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.must_change_password and not request.url.path.startswith(
        _PASSWORD_CHANGE_EXEMPT_PREFIXES
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required before accessing the application",
        )
    return user


def require_min_level(min_level: str):
    """Dependency factory: require the caller's org level to be at least
    ``min_level`` (e.g. ``require_min_level("L2")`` admits L1 and L2).

    Users without an assigned level rank as least-privileged and are always
    rejected here.
    """
    required_rank = LEVEL_RANK[min_level]

    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user_level_rank(user) > required_rank:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for your organizational level",
            )
        return user

    return checker


# Single authoritative gate for every endpoint that exposes financial data.
# Policy: L0 CEO and L1 Director ONLY. Department, designation and any other
# attribute never grant financial access.
FinancialLevel = FINANCIAL_LEVEL


def require_financial_access():
    """Dependency guarding every endpoint that exposes financial data."""
    return require_min_level(FinancialLevel)


def require_revenue_access():
    """Backwards-compatible alias of :func:`require_financial_access`."""
    return require_financial_access()


async def can_manage_project(project, user: User) -> bool:
    """Leadership (L1/L2) manages any project; otherwise only the assigned
    project lead of that specific project."""
    if user_level_rank(user) <= LEVEL_RANK["L2"]:
        return True
    return project is not None and project.project_lead_id == user.id
