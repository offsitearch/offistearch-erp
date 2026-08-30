"""Payroll models (ring r4/money).

Ported from ``app/modules/payroll/models.py``. Represents monthly payroll runs,
per-employee entries with prorated earnings, audited additions/deductions, and
per-user salary components. ``SalaryComponent`` is one record per user and keeps
a one-directional relationship to the platform ``User`` (ADR-0006 - platform
declares no outer-ring relationships).
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
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
from studioerp.enums import (
    PayrollAdjustmentCategory,
    PayrollAdjustmentKind,
    PayrollEntryStatus,
    PayrollStatus,
    enum_values,
)


class PayrollRun(TimestampMixin, Base):
    __tablename__ = "payroll_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    month: Mapped[int] = mapped_column(Integer, index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[PayrollStatus] = mapped_column(
        SAEnum(PayrollStatus, native_enum=False, length=20, values_callable=enum_values),
        default=PayrollStatus.DRAFT,
        index=True,
    )
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    processed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_method: Mapped[str | None] = mapped_column(String(15))
    payment_reference: Mapped[str | None] = mapped_column(String(60))

    entries = relationship(
        "PayrollEntry",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="PayrollEntry.user_id",
        lazy="selectin",
    )
    creator = relationship("User", foreign_keys=[created_by])
    processor = relationship("User", foreign_keys=[processed_by])


class PayrollEntry(Base):
    __tablename__ = "payroll_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payroll_run_id: Mapped[int] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    working_days: Mapped[int] = mapped_column(Integer, default=0)
    total_days: Mapped[int] = mapped_column(Integer, default=0)
    prorate: Mapped[bool] = mapped_column(Boolean, default=True)

    basic_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    hra_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    special_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    pf_deduction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    base_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    gross_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)

    payslip_path: Mapped[str | None] = mapped_column(String(255))
    entry_status: Mapped[PayrollEntryStatus] = mapped_column(
        SAEnum(
            PayrollEntryStatus, native_enum=False, length=20, values_callable=enum_values
        ),
        default=PayrollEntryStatus.INCLUDED,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_ref: Mapped[str | None] = mapped_column(String(60))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    run = relationship("PayrollRun", back_populates="entries")
    user = relationship("User", foreign_keys=[user_id])
    approver = relationship("User", foreign_keys=[approved_by])
    payer = relationship("User", foreign_keys=[paid_by])
    adjustments = relationship(
        "PayrollAdjustment",
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="PayrollAdjustment.id",
    )

    __table_args__ = (UniqueConstraint("payroll_run_id", "user_id", name="uq_payroll_entry_user"),)


class PayrollAdjustment(TimestampMixin, Base):
    __tablename__ = "payroll_adjustments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    payroll_entry_id: Mapped[int] = mapped_column(
        ForeignKey("payroll_entries.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[PayrollAdjustmentKind] = mapped_column(
        SAEnum(
            PayrollAdjustmentKind, native_enum=False, length=10, values_callable=enum_values
        ),
    )
    category: Mapped[PayrollAdjustmentCategory] = mapped_column(
        SAEnum(
            PayrollAdjustmentCategory,
            native_enum=False,
            length=30,
            values_callable=enum_values,
        ),
    )
    label: Mapped[str] = mapped_column(String(120))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    entry = relationship("PayrollEntry", back_populates="adjustments")
    creator = relationship("User", foreign_keys=[created_by])


class SalaryComponent(TimestampMixin, Base):
    __tablename__ = "salary_components"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    ctc_annual: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    basic: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    hra: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    special_allowance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    pf_deduction: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    bank_name: Mapped[str | None] = mapped_column(String(120))
    account_number: Mapped[str | None] = mapped_column(String(30))
    ifsc_code: Mapped[str | None] = mapped_column(String(15))
    effective_from: Mapped[date | None] = mapped_column(Date)

    user = relationship("User", foreign_keys=[user_id])
