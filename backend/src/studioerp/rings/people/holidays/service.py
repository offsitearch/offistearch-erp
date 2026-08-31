"""Holiday calendar CRUD operations (ring r2/people). Ported from
``app/modules/holidays/service.py``.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from studioerp.rings.people.holidays.models import Holiday
from studioerp.rings.people.holidays.schemas import HolidayCreate, HolidayUpdate
from studioerp.time import now_local


async def list_holidays(db: AsyncSession, year: int | None = None) -> list[Holiday]:
    year = year or now_local().date().year
    result = await db.execute(
        select(Holiday)
        .where(Holiday.date >= date(year, 1, 1), Holiday.date <= date(year, 12, 31))
        .order_by(Holiday.date)
    )
    return list(result.scalars().all())


async def get_holiday_dates(db: AsyncSession, from_date: date, to_date: date) -> set[date]:
    """Cross-module contract: return holiday dates in a range (used by leave)."""
    result = await db.execute(
        select(Holiday.date).where(Holiday.date >= from_date, Holiday.date <= to_date)
    )
    return set(result.scalars().all())


async def create_holiday(db: AsyncSession, payload: HolidayCreate) -> Holiday:
    holiday = Holiday(
        name=payload.name,
        date=payload.date,
        is_recurring=payload.is_recurring,
        applicable_to=payload.applicable_to,
    )
    db.add(holiday)
    await db.flush()
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def update_holiday(db: AsyncSession, holiday: Holiday, payload: HolidayUpdate) -> Holiday:
    if payload.name is not None:
        holiday.name = payload.name
    if payload.date is not None:
        holiday.date = payload.date
    if payload.is_recurring is not None:
        holiday.is_recurring = payload.is_recurring
    if payload.applicable_to is not None:
        holiday.applicable_to = payload.applicable_to
    await db.commit()
    await db.refresh(holiday)
    return holiday


async def delete_holiday(db: AsyncSession, holiday: Holiday) -> None:
    await db.delete(holiday)
    await db.commit()
