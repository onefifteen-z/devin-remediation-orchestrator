import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, Integer, String, Text, UniqueConstraint, func
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
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ESCALATED = "ESCALATED"


ACTIVE_STATUSES = {
    TaskStatus.SESSION_CREATED,
    TaskStatus.RUNNING,
    TaskStatus.PR_OPENED,
    TaskStatus.CI_FAILED,
}

POLLABLE_STATUSES = ACTIVE_STATUSES

TERMINAL_STATUSES = {
    TaskStatus.MERGED,
    TaskStatus.COMPLETED,
    TaskStatus.FAILED,
    TaskStatus.ESCALATED,
}


class TriggerSource(str, enum.Enum):
    GITHUB_WEBHOOK = "github_webhook"
    MANUAL_API = "manual_api"
    SCAN = "scan"
    SCHEDULED = "scheduled"


class TaskKind(str, enum.Enum):
    REMEDIATION = "remediation"
    SMOKE_TEST = "smoke_test"


class RemediationTask(Base):
    __tablename__ = "remediation_tasks"
    __table_args__ = (
        UniqueConstraint("github_repository", "github_issue_number", name="uq_repo_issue"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    github_delivery_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    github_repository: Mapped[str] = mapped_column(String(255))
    github_issue_number: Mapped[int] = mapped_column(Integer)
    github_issue_url: Mapped[str] = mapped_column(String(512))

    issue_title: Mapped[str] = mapped_column(String(512))
    issue_type: Mapped[str] = mapped_column(String(64), default="unknown")
    issue_labels: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_kind: Mapped[str] = mapped_column(String(32), default=TaskKind.REMEDIATION.value)
    trigger_source: Mapped[str | None] = mapped_column(String(32), nullable=True)

    devin_session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    devin_session_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    devin_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    devin_status_detail: Mapped[str | None] = mapped_column(String(64), nullable=True)
    devin_origin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    devin_service_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    devin_tags: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.RECEIVED, index=True
    )

    pr_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    pr_state: Mapped[str | None] = mapped_column(String(64), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    failure_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ci_classification_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ci_check_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ci_check_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ci_conclusion: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ci_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ci_repair_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_ci_check_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ci_repair_message_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ci_repair_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ci_passed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ci_non_code_failure_count: Mapped[int] = mapped_column(Integer, default=0)

    acu_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    acu_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    acu_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    session_size: Mapped[str | None] = mapped_column(String(8), nullable=True)
    num_user_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_devin_messages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    insights_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    insights_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    remediation_outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    implementation_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocker: Mapped[str | None] = mapped_column(Text, nullable=True)
    playbook_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    merge_notification_sent: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
