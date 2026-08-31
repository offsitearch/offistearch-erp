"""Hourly scheduler for timesheet automation (ring r3/work).

Two jobs, both idempotent and guarded by config flags:
- Friday afternoon: nudge employees who haven't submitted this week.
- Monday morning: auto-submit last week's forgotten drafts.

Started/stopped from the app lifespan (app.main). A Postgres advisory
lock (distinct key from the backup scheduler) ensures only one worker
runs the tick when several backends share the database. On non-Postgres
dev/test backends the advisory-lock probe fails gracefully and the tick
is skipped.
"""

import asyncio
import contextlib
import logging

from sqlalchemy import text

from studioerp.rings.work.timesheets import service as timesheet_service

logger = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS = 3600
ADVISORY_LOCK_KEY = "studioerp:timesheets:auto"
_task: asyncio.Task | None = None


async def _try_advisory_lock(db) -> bool:
    result = await db.execute(
        text("SELECT pg_try_advisory_lock(hashtext(:key))"), {"key": ADVISORY_LOCK_KEY}
    )
    return bool(result.scalar())


async def _unlock_advisory(db) -> None:
    await db.execute(text("SELECT pg_advisory_unlock(hashtext(:key))"), {"key": ADVISORY_LOCK_KEY})


async def _tick() -> None:
    from studioerp.db.session import get_session_factory

    async with get_session_factory()() as db:
        try:
            locked = await _try_advisory_lock(db)
        except Exception:  # noqa: BLE001 — non-Postgres dev/test backends
            logger.debug("Timesheet advisory lock unavailable — skipping", exc_info=True)
            return
        if not locked:
            logger.debug("Another worker holds the timesheet lock — skipping")
            return
        try:
            reminded = await timesheet_service.send_weekly_reminders(db)
            auto_submitted = await timesheet_service.auto_submit_finished_weeks(db)
            if reminded:
                logger.info("Weekly timesheet reminders sent: %d", reminded)
            if auto_submitted:
                logger.info("Timesheets auto-submitted: %d", auto_submitted)
        finally:
            try:
                await _unlock_advisory(db)
                await db.commit()
            except Exception:  # noqa: BLE001
                logger.exception("Releasing the timesheet advisory lock failed")


async def _loop() -> None:
    while True:
        try:
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
            await _tick()
        except asyncio.CancelledError:  # pragma: no cover — shutdown path
            raise
        except Exception:  # noqa: BLE001 — scheduler must survive any failure
            logger.exception("Timesheet scheduler iteration failed")


def start_timesheet_scheduler() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_loop())
        logger.info("Timesheet scheduler started (hourly check)")


def stop_timesheet_scheduler() -> None:
    global _task
    if _task is not None:
        _task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            pass
        _task = None