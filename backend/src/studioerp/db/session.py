"""Async engine/session (kernel k0) — created lazily.

The engine reuses connections via SQLAlchemy's real pool in every
environment except tests. Historically the external pooler
(Supavisor/PgBouncer) host caused a switch to NullPool (one fresh DB
connection per request); that meant every request paid the full
TCP+TLS+SCRAM connection cost (~3s against a far-away Supabase pooler)
which made pages take 5-10s. With the pooler in session mode (port
5432) or transaction mode (port 6543) an app-side pool is safe and
turns per-query latency from seconds to tens of milliseconds.

Prepared-statement handling stays hardened for pooler compatibility:
asyncpg's statement cache is disabled and prepared statements get
unique names so Supavisor never rejects them
(DuplicatePreparedStatementError). pool_pre_ping is off so a checkout
costs one DB round trip instead of two; pool_recycle (1800s) rotates
stale connections. Tests keep NullPool (fresh connection per request).

The engine is created lazily on first access so the kernel can be imported
and tested without a database driver installed (the asyncpg driver import is
deferred until a connection is actually requested). Runtime behaviour is
unchanged: callers use ``AsyncSessionLocal`` / ``get_db`` exactly as before.
"""

import uuid
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from studioerp.config import settings


@lru_cache
def _make_engine():
    use_null_pool = settings.environment == "test"
    engine_kwargs: dict = {
        "echo": False,
        "pool_pre_ping": False,
        "connect_args": {
            "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4().hex}__",
            "statement_cache_size": 0,
        },
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
