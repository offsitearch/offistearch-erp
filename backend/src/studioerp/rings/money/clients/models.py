"""Client CRM models (ring r4/money). Ported from ``app/modules/clients/models.py``.

The ``projects`` back-relationship is intentionally omitted: the work-ring
``Project.client_id`` column is a plain int (no FK, no relationship) because the
work ring cannot reference money-ring tables. Client↔project association is
resolved via explicit queries on ``Project.client_id`` instead.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from studioerp.db.base import Base, TimestampMixin
from studioerp.enums import ClientType, CommunicationType, DealStage, enum_values


class Client(TimestampMixin, Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    client_type: Mapped[ClientType] = mapped_column(
        SAEnum(ClientType, native_enum=False, length=20, values_callable=enum_values),
        default=ClientType.INDIVIDUAL,
    )
    company_name: Mapped[str | None] = mapped_column(String(200))
    contact_person: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(20))
    phone_secondary: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    gst_number: Mapped[str | None] = mapped_column(String(20))
    pan_number: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(40))
    referred_by: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), index=True)
    budget_range: Mapped[str | None] = mapped_column(String(40))
    interest: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    deal_stage: Mapped[DealStage] = mapped_column(
        SAEnum(DealStage, native_enum=False, length=30, values_callable=enum_values),
        default=DealStage.LEAD,
    )
    next_follow_up_date: Mapped[date | None] = mapped_column(Date)
    next_follow_up_action: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    referred_client = relationship("Client", remote_side=[id], foreign_keys=[referred_by])
    communications = relationship(
        "ClientCommunication",
        back_populates="client",
        cascade="all, delete-orphan",
        order_by="ClientCommunication.occurred_at.desc()",
    )


class ClientCommunication(Base):
    __tablename__ = "client_communications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[CommunicationType] = mapped_column(
        SAEnum(CommunicationType, native_enum=False, length=20, values_callable=enum_values)
    )
    subject: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    client = relationship("Client", back_populates="communications")
    user = relationship("User")
