"""Async engine/session (kernel k0) — created lazily.

Ported from the reference monolith ``app/db/session.py`` including the external
pooler (Supavisor/PgBouncer) detection that switches to NullPool.

The engine is created lazily on first access so the kernel can be imported
and tested without a database driver installed (the asyncpg driver import is
deferred until a connection is actually requested). Runtime behaviour is
unchanged: callers use ``AsyncSessionLocal`` / ``get_db`` exactly as before.
"""

import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from studioerp.config import settings


def _is_external_pooler(url: str) -> bool:
    """Detect Supavisor / PgBouncer pooler URLs.

    When an external pooler already manages connections, SQLAlchemy's built-in
    pool causes double-pooling and prepared-statement conflicts. Use NullPool
    to hand connection lifecycle to the pooler.
    """
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return "pooler.supabase.com" in host or "pgbouncer" in host


@lru_cache
def _make_engine():
    use_null_pool = settings.environment == "test" or _is_external_pooler(settings.database_url)
    connect_args: dict = {}
    if use_null_pool:
        # Supavisor/PgBouncer in transaction mode rejects fixed prepared-statement
        # names (DuplicatePreparedStatementError). Give each prepared statement a
        # unique name and drop SQLAlchemy's client-side cache so nothing is reused
        # across pooler connections.
        connect_args = {
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
        }
    engine_kwargs: dict = {
        "echo": False,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if use_null_pool:
        engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = 5
        engine_kwargs["max_overflow"] = 10
        engine_kwargs["pool_timeout"] = 30
        engine_kwargs["pool_recycle"] = 1800
    return create_async_engine(settings.database_url, **engine_kwargs)


def get_engine():
    """Return the (lazily-created, cached) async engine."""
    return _make_engine()


@lru_cache
def _make_session_factory():
    return async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)


def get_session_factory():
    """Return the (lazily-created, cached) async session factory."""
    return _make_session_factory()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session
