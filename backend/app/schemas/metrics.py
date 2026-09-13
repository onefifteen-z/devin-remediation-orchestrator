from pydantic import BaseModel, Field


class ThroughputPoint(BaseModel):
    date: str
    count: int


class MetricsResponse(BaseModel):
    total_tasks: int = 0
    active_tasks: int = 0
    success_rate: float = Field(
        default=0.0,
        description="MERGED / terminal tasks (MERGED + FAILED + ESCALATED).",
    )
    merge_rate: float = Field(
        default=0.0,
        description="MERGED / total tasks.",
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
        description="Tasks that reached READY_FOR_REVIEW or MERGED after CI_FAILED / tasks that hit CI_FAILED.",
    )
    total_acu: float = 0.0
    average_acu_per_task: float = 0.0
    tasks_with_prs: int = 0
    failed_tasks: int = 0
    escalated_tasks: int = 0
