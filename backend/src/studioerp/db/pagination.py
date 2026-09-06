"""Single-round-trip pagination (db kernel).

Replaces the classic ``count`` + ``select`` pair — two DB round trips per
list request — with a single query that carries ``COUNT(*) OVER()`` so the
total is read off the first row of the very same result set. On Supabase this
roughly halves list-endpoint latency (one ~225 ms Mumbai round trip saved).

``fetch_page`` strips the appended ``_total`` column before returning, so
callers unpack rows exactly as they did with the old two-query shape.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_page(db: AsyncSession, stmt, page: int = 1, page_size: int = 20):
    """Run ``stmt`` with OFFSET/LIMIT plus ``COUNT(*) OVER()`` in one query.

    Returns ``(rows, total)``. ``rows`` is a list of tuples exactly matching
    ``stmt``'s original column layout; the trailing window-count column is
    removed. ``total`` equals the number of rows the statement matches
    without OFFSET/LIMIT (used by the frontend for pagination controls).
    """
    result = await db.execute(
        stmt.add_columns(func.count().over().label("_total"))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = result.all()
    total = rows[0]._total if rows else 0
    return [row[:-1] for row in rows], total