"""Notice board models (ring r5/comms). Ported from ``app/modules/notices/models.py``.

The ``creator`` relationship is one-directional (ADR-0006): it references the
platform ``User`` by name without a back-populate.
"""

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from studioerp.db.base import Base, TimestampMixin
from studioerp.enums import NoticeImportance, enum_values


class Notice(TimestampMixin, Base):
    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[NoticeImportance] = mapped_column(
        SAEnum(NoticeImportance, native_enum=False, length=10, values_callable=enum_values),
        default=NoticeImportance.MEDIUM,
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    publish_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)

    creator = relationship("User", foreign_keys=[created_by])