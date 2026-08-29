"""Leave models (ring r2/people). Ported from ``app/modules/leave/models.py``.

One-directional relationships to the platform :class:`User` only (no back_populates)
to respect ring boundaries (ADR-0006).
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from studioerp.db.base import Base, TimestampMixin
from studioerp.enums import LeaveStatus, LeaveType, enum_values


class LeaveBalance(TimestampMixin, Base):
    __tablename__ = "leave_balance"
    __table_args__ = (
        UniqueConstraint("user_id", "leave_type", "year", name="uq_leave_balance_user_type_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    leave_type: Mapped[LeaveType] = mapped_column(
        SAEnum(LeaveType, native_enum=False, length=20, values_callable=enum_values)
    )
    year: Mapped[int] = mapped_column(Integer, index=True)
    allocated: Mapped[float] = mapped_column(Numeric(6, 2), default=0)
    used: Mapped[float] = mapped_column(Numeric(6, 2), default=0)


class Leave(TimestampMixin, Base):
    __tablename__ = "leaves"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    user = relationship("User", foreign_keys=[user_id])
    leave_type: Mapped[LeaveType] = mapped_column(
        SAEnum(LeaveType, native_enum=False, length=20, values_callable=enum_values)
    )
    from_date: Mapped[date] = mapped_column(index=True)
    to_date: Mapped[date]
    total_days: Mapped[float] = mapped_column(Numeric(6, 2))
    half_day_first: Mapped[bool] = mapped_column(Boolean, default=False)
    half_day_second: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text)
    attachment: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[LeaveStatus] = mapped_column(
        SAEnum(LeaveStatus, native_enum=False, length=20, values_callable=enum_values),
        default=LeaveStatus.PENDING,
        index=True,
    )
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    approver = relationship("User", foreign_keys=[approved_by])
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
