from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.task import ACTIVE_STATUSES, TERMINAL_STATUSES, RemediationTask, TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.ci import FailureType
from app.schemas.metrics import MetricsResponse, ThroughputPoint


class MetricsService:
    def __init__(self, db: Session):
        self.repo = TaskRepository(db)

    def compute(self) -> MetricsResponse:
        tasks = self.repo.list_all()
        if not tasks:
            return MetricsResponse()

        total = len(tasks)
        active = sum(1 for t in tasks if t.status in ACTIVE_STATUSES)
        merged = [t for t in tasks if t.status == TaskStatus.MERGED]
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        escalated = sum(1 for t in tasks if t.status == TaskStatus.ESCALATED)
        tasks_with_prs = sum(1 for t in tasks if t.pr_url is not None)
        terminal = [t for t in tasks if t.status in TERMINAL_STATUSES]

        success_rate = len(merged) / len(terminal) if terminal else 0.0
        merge_rate = len(merged) / total if total else 0.0

        mttr_values = []
        for task in merged:
            if task.merged_at and task.started_at:
                mttr_values.append((task.merged_at - task.started_at).total_seconds())
        median_mttr = _median(mttr_values) if mttr_values else None

        now = datetime.now(UTC)
        seven_days_ago = now - timedelta(days=7)
        throughput_7d = sum(
            1 for t in tasks if _ensure_aware(t.created_at) >= seven_days_ago
        )
        throughput_by_day = _throughput_by_day(tasks, days=7)

        ci_metrics = _compute_ci_metrics(tasks)

        acu_values = [t.acu_used for t in tasks if t.acu_used is not None]
        total_acu = sum(acu_values)
        average_acu = total_acu / len(acu_values) if acu_values else 0.0

        return MetricsResponse(
            total_tasks=total,
            active_tasks=active,
            success_rate=round(success_rate, 4),
            merge_rate=round(merge_rate, 4),
            median_mttr_seconds=median_mttr,
            throughput_7d=throughput_7d,
            throughput_by_day=throughput_by_day,
            ci_recovery_rate=ci_metrics["ci_recovery_rate"],
            tasks_with_ci_failures=ci_metrics["tasks_with_ci_failures"],
            code_ci_failures=ci_metrics["code_ci_failures"],
            transient_ci_failures=ci_metrics["transient_ci_failures"],
            infra_ci_failures=ci_metrics["infra_ci_failures"],
            unknown_ci_failures=ci_metrics["unknown_ci_failures"],
            ci_repair_attempts=ci_metrics["ci_repair_attempts"],
            ci_repair_successes=ci_metrics["ci_repair_successes"],
            total_acu=round(total_acu, 2),
            average_acu_per_task=round(average_acu, 2),
            tasks_with_prs=tasks_with_prs,
            failed_tasks=failed,
            escalated_tasks=escalated,
        )


def _compute_ci_metrics(tasks: list[RemediationTask]) -> dict:
    tasks_with_ci_failures = [t for t in tasks if t.ci_failure_at is not None]
    ci_repair_successes = sum(
        1 for t in tasks_with_ci_failures if t.ci_repair_verified_at is not None
    )
    ci_recovery_rate = (
        ci_repair_successes / len(tasks_with_ci_failures)
        if tasks_with_ci_failures
        else 0.0
    )

    return {
        "tasks_with_ci_failures": len(tasks_with_ci_failures),
        "code_ci_failures": sum(
            1 for t in tasks_with_ci_failures if t.failure_type == FailureType.CODE_FAILURE.value
        ),
        "transient_ci_failures": sum(
            1
            for t in tasks_with_ci_failures
            if t.failure_type == FailureType.TRANSIENT_FAILURE.value
        ),
        "infra_ci_failures": sum(
            1 for t in tasks_with_ci_failures if t.failure_type == FailureType.INFRA_FAILURE.value
        ),
        "unknown_ci_failures": sum(
            1 for t in tasks_with_ci_failures if t.failure_type == FailureType.UNKNOWN.value
        ),
        "ci_repair_attempts": sum(t.ci_repair_attempts for t in tasks),
        "ci_repair_successes": ci_repair_successes,
        "ci_recovery_rate": round(ci_recovery_rate, 4),
    }


def _median(values: list[float]) -> float:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 0:
        return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2
    return sorted_vals[mid]


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _throughput_by_day(tasks: list[RemediationTask], days: int) -> list[ThroughputPoint]:
    now = datetime.now(UTC).date()
    counts: dict[str, int] = {}
    for i in range(days):
        day = now - timedelta(days=days - 1 - i)
        counts[day.isoformat()] = 0

    for task in tasks:
        created = _ensure_aware(task.created_at).date()
        key = created.isoformat()
        if key in counts:
            counts[key] += 1

    return [ThroughputPoint(date=date, count=count) for date, count in counts.items()]
