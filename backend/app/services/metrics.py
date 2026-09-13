from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.task import ACTIVE_STATUSES, TERMINAL_STATUSES, RemediationTask, TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.ci import FailureType
from app.schemas.devin_consumption import ConsumptionResponse
from app.schemas.metrics import MetricsResponse, ThroughputPoint
from app.services.devin import DevinClient
from app.services.devin_analytics import DevinAnalyticsService
from app.services.task_classification import is_production_remediation


class MetricsService:
    def __init__(self, db: Session):
        self.repo = TaskRepository(db)

    def compute(self) -> MetricsResponse:
        tasks = self.repo.list_all()
        if not tasks:
            return MetricsResponse()

        total = len(tasks)
        production_tasks = [task for task in tasks if is_production_remediation(task)]
        active = sum(1 for t in tasks if t.status in ACTIVE_STATUSES)
        merged = [t for t in tasks if t.status == TaskStatus.MERGED]
        merged_production = [
            t for t in production_tasks if t.status == TaskStatus.MERGED
        ]
        failed = sum(1 for t in tasks if t.status == TaskStatus.FAILED)
        escalated = sum(1 for t in tasks if t.status == TaskStatus.ESCALATED)
        tasks_with_prs = sum(1 for t in tasks if t.pr_url is not None)
        terminal = [t for t in tasks if t.status in TERMINAL_STATUSES]
        production_terminal = [
            t for t in production_tasks if t.status in TERMINAL_STATUSES
        ]

        success_rate = (
            len(merged_production) / len(production_terminal)
            if production_terminal
            else 0.0
        )
        merge_rate = (
            len(merged_production) / len(production_tasks) if production_tasks else 0.0
        )

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

        verified_values = [
            t.acu_used for t in tasks if t.acu_verified and t.acu_used is not None
        ]
        verified_total_acu = sum(verified_values)
        average_verified_acu = (
            verified_total_acu / len(verified_values) if verified_values else 0.0
        )

        consumption_api_available = None
        devin_org_total_acus = None

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
            verified_total_acu=round(verified_total_acu, 2),
            average_verified_acu_per_task=round(average_verified_acu, 2),
            consumption_api_available=consumption_api_available,
            devin_org_total_acus=devin_org_total_acus,
            tasks_with_prs=tasks_with_prs,
            failed_tasks=failed,
            escalated_tasks=escalated,
        )

    async def compute_with_analytics(self) -> MetricsResponse:
        metrics = self.compute()
        settings = get_settings()
        if not settings.devin_api_key or not settings.devin_org_id:
            return metrics

        client = DevinClient(settings)
        analytics = DevinAnalyticsService(client)
        try:
            seven_days_ago = int((datetime.now(UTC) - timedelta(days=7)).timestamp())
            result = await analytics.get_org_consumption_window(time_after=seven_days_ago)
            metrics.consumption_api_available = analytics.consumption_api_available
            if isinstance(result, ConsumptionResponse):
                metrics.devin_org_total_acus = round(result.total_acus, 2)
        finally:
            await client.close()
        return metrics


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
