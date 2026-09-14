from app.models.task import RemediationTask, TaskKind, TriggerSource


def trigger_source_from_event_source(source: str) -> str:
    mapping = {
        "github": TriggerSource.GITHUB_WEBHOOK.value,
        "api": TriggerSource.MANUAL_API.value,
        "scan": TriggerSource.SCAN.value,
        "scheduled": TriggerSource.SCHEDULED.value,
    }
    return mapping.get(source, TriggerSource.GITHUB_WEBHOOK.value)


def task_kind_from_title(issue_title: str) -> str:
    if "smoke test" in (issue_title or "").lower():
        return TaskKind.SMOKE_TEST.value
    return TaskKind.REMEDIATION.value


def is_smoke_test_task(task: RemediationTask) -> bool:
    return (task.task_kind or TaskKind.REMEDIATION.value) == TaskKind.SMOKE_TEST.value


def is_production_remediation(task: RemediationTask) -> bool:
    return not is_smoke_test_task(task)
