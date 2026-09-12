import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    SESSION_CREATED = "SESSION_CREATED"
    RUNNING = "RUNNING"
    PR_OPENED = "PR_OPENED"
    CI_FAILED = "CI_FAILED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    MERGED = "MERGED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


ACTIVE_STATUSES = {
    TaskStatus.SESSION_CREATED,
    TaskStatus.RUNNING,
    TaskStatus.PR_OPENED,
    TaskStatus.CI_FAILED,
}

TERMINAL_STATUSES = {
    TaskStatus.MERGED,
    TaskStatus.FAILED,
    TaskStatus.ESCALATED,
}


class RemediationTask(Base):
    __tablename__ = "remediation_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    github_delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    github_repository: Mapped[str] = mapped_column(String(255))
    github_issue_number: Mapped[int] = mapped_column(Integer)
    github_issue_url: Mapped[str] = mapped_column(String(512))

    issue_title: Mapped[str] = mapped_column(String(512))
    issue_type: Mapped[str] = mapped_column(String(64), default="unknown")

    devin_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    devin_session_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.RECEIVED, index=True
    )

    pr_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    acu_used: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
