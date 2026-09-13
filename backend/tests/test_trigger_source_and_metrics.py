from types import SimpleNamespace

from app.models.task import TaskStatus, TriggerSource
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.metrics import MetricsService
from app.services.task_classification import (
    is_production_remediation,
    is_smoke_test_task,
    trigger_source_from_event_source,
)


def test_trigger_source_from_event_source_mapping():
    assert trigger_source_from_event_source("github") == TriggerSource.GITHUB_WEBHOOK.value
    assert trigger_source_from_event_source("api") == TriggerSource.MANUAL_API.value
    assert trigger_source_from_event_source("scan") == TriggerSource.SCAN.value


def test_is_smoke_test_task_detects_title():
    task = SimpleNamespace(issue_title="Webhook integration smoke test")
    assert is_smoke_test_task(task) is True
    assert is_production_remediation(task) is False


def test_merge_rate_excludes_smoke_test_tasks(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="prod-merged-001",
            github_repository="owner/superset",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/superset/issues/1",
            issue_title="Real remediation",
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    merged = repo.get_by_issue("owner/superset", 1)
    assert merged is not None
    repo.update_status(
        merged,
        TaskStatus.MERGED,
    )
    repo.create_task(
        TaskCreate(
            github_delivery_id="smoke-001",
            github_repository="owner/superset",
            github_issue_number=2,
            github_issue_url="https://github.com/owner/superset/issues/2",
            issue_title="Webhook integration smoke test",
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    smoke = repo.get_by_issue("owner/superset", 2)
    assert smoke is not None
    repo.update_status(smoke, TaskStatus.MERGED)

    metrics = MetricsService(db_session).compute()
    assert metrics.merge_rate == 1.0


def test_webhook_task_persists_trigger_source(client, webhook_secret):
    from unittest.mock import AsyncMock, patch

    from tests.conftest import make_issue_labeled_payload, signed_webhook_request

    with patch("app.api.webhooks._process_task_background", new_callable=AsyncMock):
        payload = make_issue_labeled_payload(issue_number=99999)
        response = signed_webhook_request(
            client,
            payload,
            webhook_secret,
            delivery_id="trigger-source-webhook-001",
        )
        assert response.status_code == 202

    api_response = client.get("/api/tasks")
    item = next(i for i in api_response.json()["items"] if i["github_issue_number"] == 99999)
    assert item["trigger_source"] == TriggerSource.GITHUB_WEBHOOK.value
