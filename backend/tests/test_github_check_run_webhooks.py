from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.config import get_settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.ci import FailureType
from app.schemas.task import TaskCreate
from app.services.metrics import MetricsService
from tests.conftest import (
    load_fixture,
    make_check_run_payload,
    signed_check_run_webhook_request,
)


def _create_task_with_pr(
    db_session,
    pr_url: str,
    status: TaskStatus = TaskStatus.PR_OPENED,
    delivery_id: str = "check-run-task-001",
    devin_session_id: str | None = "devin-session-abc",
):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=delivery_id,
            github_repository="owner/superset",
            github_issue_number=44176,
            github_issue_url="https://github.com/owner/superset/issues/44176",
            issue_title="Test issue",
        )
    )
    return repo.update_task(
        task,
        pr_url=pr_url,
        status=status,
        devin_session_id=devin_session_id,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _refresh_task(db_session, task_id: int):
    db_session.expire_all()
    return TaskRepository(db_session).get_by_id(task_id)


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_valid_check_run_failure_accepted(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-failure-001"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "processed"
    assert data["task_id"] == task.id

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.failure_type == FailureType.CODE_FAILURE.value
    assert refreshed.ci_check_name == "Python Unit Tests"
    assert refreshed.ci_repair_attempts == 0


def test_invalid_hmac_rejected(client):
    payload = load_fixture("check_run_failure.json")
    response = client.post(
        "/webhooks/github",
        json=payload,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "check_run",
            "X-GitHub-Delivery": "cr-bad-sig",
            "X-Hub-Signature-256": "sha256=invalid",
        },
    )
    assert response.status_code == 401


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_successful_check_ignored(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_success.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-success-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"
    mock_repair.assert_not_called()


def test_non_terminal_check_ignored(client, webhook_secret):
    payload = make_check_run_payload(status="in_progress", conclusion=None)
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-in-progress-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_duplicate_delivery_ignored(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)
    payload = load_fixture("check_run_failure.json")

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        first = signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-delivery"
        )
        second = signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-delivery"
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["outcome"] == "duplicate"
    assert mock_repair.call_count == 1


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_duplicate_check_run_ignored(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)
    payload = load_fixture("check_run_failure.json")

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        first = signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-check-1"
        )
        second = signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-check-2"
        )

    assert first.json()["outcome"] == "processed"
    assert second.json()["outcome"] == "already_processed"
    assert mock_repair.call_count == 1


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_check_run_maps_to_correct_task(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-map-001"
    )

    assert response.json()["task_id"] == task.id
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.ci_conclusion == "failure"


def test_unrelated_pr_produces_no_task_action(client, webhook_secret):
    payload = load_fixture("check_run_failure.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-unrelated-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "no_matching_task"


def test_missing_task_returns_no_matching_task(client, webhook_secret):
    payload = load_fixture("check_run_failure.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-no-task-001"
    )
    assert response.json()["outcome"] == "no_matching_task"


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_code_failure_triggers_one_send_message(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url, devin_session_id="session-xyz")

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        payload = load_fixture("check_run_failure.json")
        response = signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-send-001"
        )

    assert response.json()["outcome"] == "processed"
    mock_repair.assert_called_once()
    args = mock_repair.call_args[0]
    assert args[0] == response.json()["task_id"]
    assert "CI failure" in args[1]


@patch("app.api.webhooks.DevinClient")
def test_send_message_uses_existing_session(mock_devin_cls, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url, devin_session_id="session-xyz")

    mock_client = mock_devin_cls.return_value
    mock_client.send_message = AsyncMock()
    mock_client.close = AsyncMock()

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        payload = load_fixture("check_run_failure.json")
        signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-session-001"
        )

    mock_client.send_message.assert_called_once()
    assert mock_client.send_message.call_args[0][0] == "session-xyz"
    mock_client.create_session.assert_not_called()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_infra_failure_does_not_trigger_devin(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_infra.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-infra-001"
    )

    assert response.json()["outcome"] == "processed"
    refreshed = _refresh_task(db_session, response.json()["task_id"])
    assert refreshed.failure_type == FailureType.INFRA_FAILURE.value
    mock_repair.assert_not_called()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_transient_failure_does_not_trigger_devin(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_cancelled.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-cancel-001"
    )

    refreshed = _refresh_task(db_session, response.json()["task_id"])
    assert refreshed.failure_type == FailureType.TRANSIENT_FAILURE.value
    mock_repair.assert_not_called()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_unknown_failure_does_not_trigger_devin(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_unknown.json")
    response = signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-unknown-001"
    )

    refreshed = _refresh_task(db_session, response.json()["task_id"])
    assert refreshed.failure_type == FailureType.UNKNOWN.value
    mock_repair.assert_not_called()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_repair_attempt_increments_atomically(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    payload2 = make_check_run_payload(check_run_id=987654399)

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-inc-1"
        )
        signed_check_run_webhook_request(
            client, payload2, webhook_secret, delivery_id="cr-inc-2"
        )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.ci_repair_attempts == 2


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_max_attempts_escalates(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)
    repo = TaskRepository(db_session)
    repo.update_task(task, ci_repair_attempts=2)

    payload = make_check_run_payload(check_run_id=987654400)
    signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-max-001"
    )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status == TaskStatus.ESCALATED
    assert refreshed.escalation_reason is not None
    mock_repair.assert_not_called()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_duplicate_event_cannot_trigger_duplicate_message(
    mock_repair, client, webhook_secret, db_session
):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)
    payload = load_fixture("check_run_failure.json")

    with patch.dict("os.environ", {"DEVIN_LIVE_ENABLED": "true"}):
        get_settings.cache_clear()
        signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-msg-1"
        )
        signed_check_run_webhook_request(
            client, payload, webhook_secret, delivery_id="cr-dup-msg-2"
        )

    assert mock_repair.call_count == 1


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_ci_metadata_persists(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-meta-001"
    )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.ci_check_name == "Python Unit Tests"
    assert refreshed.ci_check_url is not None
    assert refreshed.ci_failure_at is not None
    assert refreshed.last_ci_check_run_id == 987654321


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_classification_reason_persists(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_cancelled.json")
    signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-reason-001"
    )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.ci_classification_reason is not None
    assert "transient" in refreshed.ci_classification_reason.lower()


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_dashboard_api_exposes_ci_metadata(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-api-001"
    )

    response = client.get("/api/tasks")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["ci_check_name"] == "Python Unit Tests"
    assert item["failure_type"] == FailureType.CODE_FAILURE.value
    assert item["ci_repair_attempts"] == 0


@patch("app.api.webhooks._send_ci_repair_message_background", new_callable=AsyncMock)
def test_metrics_remain_honest(mock_repair, client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = load_fixture("check_run_failure.json")
    signed_check_run_webhook_request(
        client, payload, webhook_secret, delivery_id="cr-metrics-001"
    )

    db_session.expire_all()
    metrics = MetricsService(db_session).compute()
    assert metrics.tasks_with_ci_failures == 1
    assert metrics.code_ci_failures == 1
    assert metrics.ci_repair_attempts == 0
    assert metrics.ci_repair_successes == 0

    success_payload = load_fixture("check_run_success.json")
    signed_check_run_webhook_request(
        client, success_payload, webhook_secret, delivery_id="cr-metrics-success"
    )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.ci_repair_verified_at is not None

    db_session.expire_all()
    metrics_after = MetricsService(db_session).compute()
    assert metrics_after.ci_repair_successes == 1
    assert metrics_after.ci_recovery_rate == 1.0
