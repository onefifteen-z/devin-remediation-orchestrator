from sqlalchemy import func, or_

from app.models.task import RemediationTask, TaskKind, TriggerSource

SMOKE_TEST_ISSUE_TYPE = "dummy"


def trigger_source_from_event_source(source: str) -> str:
    mapping = {
        "github": TriggerSource.GITHUB_WEBHOOK.value,
        "api": TriggerSource.MANUAL_API.value,
        "scan": TriggerSource.SCAN.value,
        "scheduled": TriggerSource.SCHEDULED.value,
    }
    return mapping.get(source, TriggerSource.GITHUB_WEBHOOK.value)


def task_kind_from_title(issue_title: str, issue_type: str | None = None) -> str:
    if (issue_type or "").lower() == SMOKE_TEST_ISSUE_TYPE:
        return TaskKind.SMOKE_TEST.value
    if "smoke test" in (issue_title or "").lower():
        return TaskKind.SMOKE_TEST.value
    return TaskKind.REMEDIATION.value


def is_smoke_test_task(task: RemediationTask) -> bool:
    if (task.task_kind or TaskKind.REMEDIATION.value) == TaskKind.SMOKE_TEST.value:
        return True
    return (task.issue_type or "").lower() == SMOKE_TEST_ISSUE_TYPE


def smoke_test_sql_condition():
    return or_(
        RemediationTask.task_kind == TaskKind.SMOKE_TEST.value,
        func.lower(RemediationTask.issue_type) == SMOKE_TEST_ISSUE_TYPE,
    )


def is_production_remediation(task: RemediationTask) -> bool:
    return not is_smoke_test_task(task)
