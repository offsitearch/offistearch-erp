"""Holiday calendar model (ring r2/people). Ported from ``app/modules/holidays/models.py``."""

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, String
from sqlalchemy.orm import Mapped, mapped_column

from studioerp.db.base import Base, TimestampMixin


class Holiday(TimestampMixin, Base):
    __tablename__ = "holidays"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, default=False)
    applicable_to: Mapped[str] = mapped_column(String(40), default="all")
