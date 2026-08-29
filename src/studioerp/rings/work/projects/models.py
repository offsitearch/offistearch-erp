"""Project, project team and project phase models (ring r3/work). Ported from
``app/modules/projects/models.py``.

Per the ring contract the ``work`` ring must not import the ``money`` ring
(clients). ``client_id`` is therefore kept as a plain nullable integer column
with no FK and no relationship; client_name resolution is deferred until the
money/clients ring lands. User relationships stay one-directional (ADR-0006).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from studioerp.db.base import Base, TimestampMixin
from studioerp.enums import PhaseStatus, ProjectStatus, ProjectType, enum_values


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_code: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    project_type: Mapped[ProjectType] = mapped_column(
        SAEnum(ProjectType, native_enum=False, length=20, values_callable=enum_values)
    )
    category: Mapped[str | None] = mapped_column(String(80))
    # client_id intentionally has NO FK: clients live in the money ring and the
    # work ring must not import it. The int is retained for parity + future
    # cross-ring resolution via the API composition root.
    client_id: Mapped[int | None] = mapped_column(Integer, index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    plot_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    built_up_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    no_of_floors: Mapped[str | None] = mapped_column(String(20))
    coordinates: Mapped[str | None] = mapped_column(String(80))
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    studio_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)
    fee_type: Mapped[str | None] = mapped_column(String(20))
    fee_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, native_enum=False, length=20, values_callable=enum_values),
        default=ProjectStatus.DRAFT,
        index=True,
    )
    project_lead_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    priority: Mapped[str] = mapped_column(String(10), default="medium")
    progress_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    hours_logged: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    lead = relationship("User", foreign_keys=[project_lead_id])
    team = relationship(
        "ProjectTeam",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectTeam.id",
    )
    phases = relationship(
        "ProjectPhase",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectPhase.order_index",
    )


class ProjectTeam(Base):
    __tablename__ = "project_team"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_team_member"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str | None] = mapped_column(String(80))

    project = relationship("Project", back_populates="team")
    user = relationship("User", foreign_keys=[user_id])


class ProjectPhase(TimestampMixin, Base):
    __tablename__ = "project_phases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    order_index: Mapped[int] = mapped_column(default=0)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[PhaseStatus] = mapped_column(
        SAEnum(PhaseStatus, native_enum=False, length=20, values_callable=enum_values),
        default=PhaseStatus.NOT_STARTED,
    )
    completion_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    studio_fee: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=1)

    project = relationship("Project", back_populates="phases")
