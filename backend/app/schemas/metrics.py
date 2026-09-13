from pydantic import BaseModel, Field


class ThroughputPoint(BaseModel):
    date: str
    count: int


class MetricsResponse(BaseModel):
    total_tasks: int = 0
    active_tasks: int = 0
    success_rate: float = Field(
        default=0.0,
        description="MERGED / terminal production remediations (excludes smoke tests).",
    )
    merge_rate: float = Field(
        default=0.0,
        description="MERGED production remediations / production remediation tasks (excludes smoke tests).",
    )
    median_mttr_seconds: float | None = Field(
        default=None,
        description="Median (merged_at - started_at) for MERGED tasks only.",
    )
    throughput_7d: int = Field(
        default=0,
        description="Tasks created in the last 7 days.",
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
    total_acu: float = 0.0
    average_acu_per_task: float = 0.0
    tasks_with_prs: int = 0
    failed_tasks: int = 0
    escalated_tasks: int = 0
