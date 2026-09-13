from app.models.task import RemediationTask, TriggerSource


def trigger_source_from_event_source(source: str) -> str:
    mapping = {
        "github": TriggerSource.GITHUB_WEBHOOK.value,
        "api": TriggerSource.MANUAL_API.value,
        "scan": TriggerSource.SCAN.value,
        "scheduled": TriggerSource.SCHEDULED.value,
    }
    return mapping.get(source, TriggerSource.GITHUB_WEBHOOK.value)


def is_smoke_test_task(task: RemediationTask) -> bool:
    return "smoke test" in (task.issue_title or "").lower()


def is_production_remediation(task: RemediationTask) -> bool:
    return not is_smoke_test_task(task)
