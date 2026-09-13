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
    trigger_source: str = "github_webhook"
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
    trigger_source: str | None = None
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
    failure_type: str | None = None
    ci_classification_reason: str | None = None
    ci_check_name: str | None = None
    ci_check_url: str | None = None
    ci_conclusion: str | None = None
    ci_failure_at: datetime | None = None
    ci_repair_attempts: int = 0
    max_ci_repair_attempts: int = Field(
        default=2,
        description="Maximum Devin CI repair attempts allowed for this task.",
    )
    last_ci_check_run_id: int | None = None
    ci_repair_message_sent_at: datetime | None = None
    ci_repair_verified_at: datetime | None = None
    ci_non_code_failure_count: int = 0
    acu_used: float | None
    acu_source: str | None = None
    acu_verified: bool = False
    remediation_outcome: str | None = None
    root_cause: str | None = None
    implementation_summary: str | None = None
    structured_result_json: str | None = None
    blocker: str | None = None
    playbook_id: str | None = None
    created_at: datetime
    updated_at: datetime

    mttr_seconds: float | None = Field(
        default=None,
        description="Time from started_at to merged_at for merged tasks only.",
    )

    @classmethod
    def from_orm_task(cls, task, max_ci_repair_attempts: int = 2) -> "TaskResponse":
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
            trigger_source=task.trigger_source,
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
            failure_type=task.failure_type,
            ci_classification_reason=task.ci_classification_reason,
            ci_check_name=task.ci_check_name,
            ci_check_url=task.ci_check_url,
            ci_conclusion=task.ci_conclusion,
            ci_failure_at=task.ci_failure_at,
            ci_repair_attempts=task.ci_repair_attempts,
            max_ci_repair_attempts=max_ci_repair_attempts,
            last_ci_check_run_id=task.last_ci_check_run_id,
            ci_repair_message_sent_at=task.ci_repair_message_sent_at,
            ci_repair_verified_at=task.ci_repair_verified_at,
            ci_non_code_failure_count=task.ci_non_code_failure_count,
            acu_used=task.acu_used,
            acu_source=task.acu_source,
            acu_verified=task.acu_verified,
            remediation_outcome=task.remediation_outcome,
            root_cause=task.root_cause,
            implementation_summary=task.implementation_summary,
            structured_result_json=task.structured_result_json,
            blocker=task.blocker,
            playbook_id=task.playbook_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            mttr_seconds=mttr,
        )


class TaskListResponse(BaseModel):
    items: list[TaskResponse]
    total: int
