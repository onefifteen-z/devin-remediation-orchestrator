from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.task import TaskStatus


class RemediationEvent(BaseModel):
    """Normalized remediation trigger, decoupled from GitHub payload shape."""

    github_delivery_id: str
    source: str = "github"
    github_repository: str
    github_issue_number: int
    github_issue_url: str
    issue_title: str
    issue_body: str | None = None
    issue_type: str = "unknown"
    action: str | None = None


class TaskCreate(BaseModel):
    github_delivery_id: str
    github_repository: str
    github_issue_number: int
    github_issue_url: str
    issue_title: str
    issue_type: str = "unknown"
    max_retries: int = 3


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    github_delivery_id: str
    github_repository: str
    github_issue_number: int
    github_issue_url: str
    issue_title: str
    issue_type: str
    devin_session_id: str | None
    devin_session_url: str | None
    devin_status: str | None = None
    devin_status_detail: str | None = None
    devin_origin: str | None = None
    devin_service_user_id: str | None = None
    devin_tags: str | None = None
    status: TaskStatus = Field(description="Workflow status (business remediation progress).")
    pr_url: str | None
    pr_state: str | None = None
    retry_count: int
    max_retries: int
    started_at: datetime | None
    completed_at: datetime | None
    merged_at: datetime | None
    failure_reason: str | None
    escalation_reason: str | None
    acu_used: float | None
    created_at: datetime
    updated_at: datetime

    mttr_seconds: float | None = Field(
        default=None,
        description="Time from started_at to merged_at for merged tasks only.",
    )

    @classmethod
    def from_orm_task(cls, task) -> "TaskResponse":
        mttr = None
        if task.merged_at and task.started_at:
            mttr = (task.merged_at - task.started_at).total_seconds()
        return cls(
            id=task.id,
            github_delivery_id=task.github_delivery_id,
            github_repository=task.github_repository,
            github_issue_number=task.github_issue_number,
            github_issue_url=task.github_issue_url,
            issue_title=task.issue_title,
            issue_type=task.issue_type,
            devin_session_id=task.devin_session_id,
            devin_session_url=task.devin_session_url,
            devin_status=task.devin_status,
            devin_status_detail=task.devin_status_detail,
            devin_origin=task.devin_origin,
            devin_service_user_id=task.devin_service_user_id,
            devin_tags=task.devin_tags,
            status=task.status,
            pr_url=task.pr_url,
            pr_state=task.pr_state,
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            started_at=task.started_at,
            completed_at=task.completed_at,
            merged_at=task.merged_at,
            failure_reason=task.failure_reason,
            escalation_reason=task.escalation_reason,
            acu_used=task.acu_used,
            created_at=task.created_at,
            updated_at=task.updated_at,
            mttr_seconds=mttr,
        )


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
