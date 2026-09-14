from pydantic import BaseModel, Field

from app.schemas.devin_metrics import OrgMetricsSnapshot


class ThroughputPoint(BaseModel):
    date: str
    count: int


class MetricsResponse(BaseModel):
    total_tasks: int = Field(
        default=0,
        description="Production remediation tasks only (excludes smoke_test task_kind).",
    )
    active_tasks: int = Field(
        default=0,
        description="Active production remediation tasks (excludes smoke_test).",
    )
    success_rate: float = Field(
        default=0.0,
        description="MERGED / terminal production remediations (excludes smoke_test).",
    )
    merge_rate: float = Field(
        default=0.0,
        description="MERGED production remediations / all production remediation tasks.",
    )
    median_mttr_seconds: float | None = Field(
        default=None,
        description="Median (merged_at - started_at) for MERGED production remediations only.",
    )
    throughput_7d: int = Field(
        default=0,
        description="Production remediation tasks created in the last 7 days.",
    )
    throughput_by_day: list[ThroughputPoint] = Field(default_factory=list)
    ci_recovery_rate: float = Field(
        default=0.0,
        description="Tasks with verified CI recovery / tasks with CI failures.",
    )
    tasks_with_ci_failures: int = Field(
        default=0,
        description="Tasks with ci_failure_at recorded.",
    )
    code_ci_failures: int = Field(default=0)
    transient_ci_failures: int = Field(default=0)
    infra_ci_failures: int = Field(default=0)
    unknown_ci_failures: int = Field(default=0)
    ci_repair_attempts: int = Field(
        default=0,
        description="Sum of ci_repair_attempts across tasks.",
    )
    ci_repair_successes: int = Field(
        default=0,
        description="Tasks where ci_repair_verified_at is set (GitHub evidence of recovery).",
    )
    total_acu: float = Field(
        default=0.0,
        description="Verified ACU total (same as verified_total_acu; excludes unverified values).",
    )
    average_acu_per_task: float = Field(
        default=0.0,
        description="Average verified ACU per task with acu_verified=true.",
    )
    verified_total_acu: float = Field(
        default=0.0,
        description="Sum of acu_used where acu_verified=true for production remediations.",
    )
    average_verified_acu_per_task: float = Field(
        default=0.0,
        description="Average acu_used for tasks with acu_verified=true.",
    )
    consumption_api_available: bool | None = Field(
        default=None,
        description=(
            "Whether Devin consumption API was available on last metrics probe. "
            "True only means the request succeeded: consumption reporting via the "
            "API is available only for organizations on Enterprise plans, and "
            "other plans return an empty ledger with a 200."
        ),
    )
    devin_org_total_acus: float | None = Field(
        default=None,
        description=(
            "Organization ACU total from Devin analytics when available. Stays 0 "
            "on non-Enterprise plans regardless of actual usage."
        ),
    )
    devin_org_metrics: OrgMetricsSnapshot | None = Field(
        default=None,
        description=(
            "Devin org-wide metrics for the reporting window. Counts every org "
            "session, so it is not comparable to the task-derived metrics above."
        ),
    )
    org_metrics_window_days: int = Field(
        default=30,
        description="Length of the window used for devin_org_metrics.",
    )
    tasks_with_prs: int = 0
    failed_tasks: int = 0
    escalated_tasks: int = 0
