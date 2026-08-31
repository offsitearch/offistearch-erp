"""Task and checklist models (ring r3/work). Ported from ``app/modules/tasks/models.py``.

Sibling relationships (project / phase) reference the ``work`` ring's own
projects models; user relationships stay one-directional (ADR-0006).
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import ARRAY, Boolean, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Enum as SAEnum

from studioerp.db.base import Base, TimestampMixin
from studioerp.enums import TaskPriority, TaskStatus, enum_values


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    phase_id: Mapped[int | None] = mapped_column(ForeignKey("project_phases.id"), index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    priority: Mapped[TaskPriority] = mapped_column(
        SAEnum(TaskPriority, native_enum=False, length=10, values_callable=enum_values),
        default=TaskPriority.MEDIUM,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, native_enum=False, length=15, values_callable=enum_values),
        default=TaskStatus.TODO,
        index=True,
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(40)))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    project = relationship("Project")
    phase = relationship("ProjectPhase")
    assignee = relationship("User", foreign_keys=[assigned_to])
    checklist = relationship(
        "TaskChecklist",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskChecklist.id",
    )


class TaskChecklist(Base):
    __tablename__ = "task_checklist"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    text: Mapped[str] = mapped_column(String(255))
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)

    task = relationship("Task", back_populates="checklist")
