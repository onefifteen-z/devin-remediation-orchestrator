from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.metrics import MetricsService
from tests.conftest import (
    load_fixture,
    make_pull_request_payload,
    signed_pr_webhook_request,
    signed_webhook_request,
)
from tests.conftest import make_issue_labeled_payload


def _create_task_with_pr(
    db_session,
    pr_url: str | None,
    status: TaskStatus = TaskStatus.RUNNING,
    delivery_id: str = "pr-webhook-task-001",
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
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _refresh_task(db_session, task_id: int):
    db_session.expire_all()
    return TaskRepository(db_session).get_by_id(task_id)


def test_pr_opened_associates_with_correct_task(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.RUNNING)

    payload = load_fixture("pull_request_opened.json")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-opened-001"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "processed"
    assert data["task_id"] == task.id

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.pr_url == pr_url
    assert refreshed.pr_state == "open"
    assert refreshed.status == TaskStatus.PR_OPENED


def test_unrelated_pr_ignored(client, webhook_secret):
    payload = load_fixture("pull_request_opened.json")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-unrelated-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


def test_unrelated_pr_does_not_bind_lone_unassigned_task(
    client, webhook_secret, db_session
):
    task = _create_task_with_pr(
        db_session,
        pr_url=None,
        status=TaskStatus.RUNNING,
        delivery_id="unassigned-task-001",
    )

    payload = load_fixture("pull_request_opened.json")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-unassigned-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.pr_url is None
    assert refreshed.status == TaskStatus.RUNNING


def test_pr_url_and_state_persisted(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url)

    payload = make_pull_request_payload(action="opened")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-persist-001"
    )

    assert response.status_code == 200
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.pr_url == pr_url
    assert refreshed.pr_state == "open"


def test_synchronize_updates_metadata_without_new_task(
    client, webhook_secret, db_session
):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.PR_OPENED)

    payload = load_fixture("pull_request_synchronize.json")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-sync-001"
    )

    assert response.status_code == 200
    assert response.json()["outcome"] == "processed"
    assert client.get("/api/tasks").json()["total"] == 1


def test_closed_unmerged_does_not_become_merged(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.READY_FOR_REVIEW)

    payload = load_fixture("pull_request_closed_unmerged.json")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-closed-unmerged-001"
    )

    assert response.status_code == 200
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status == TaskStatus.ESCALATED
    assert refreshed.escalation_reason == "Pull request closed without merge."
    assert refreshed.merged_at is None
    assert refreshed.completed_at is not None


def test_closed_merged_becomes_merged(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.READY_FOR_REVIEW)

    payload = load_fixture("pull_request_closed_merged.json")
    with patch(
        "app.api.webhooks._post_merge_actions_background",
        new=AsyncMock(),
    ):
        response = signed_pr_webhook_request(
            client, payload, webhook_secret, delivery_id="pr-merged-001"
        )

    assert response.status_code == 200
    assert response.json()["outcome"] == "merged"
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status == TaskStatus.MERGED
    expected_merged = datetime(2026, 3, 13, 12, 0, tzinfo=UTC)
    merged_at = refreshed.merged_at.replace(tzinfo=UTC) if refreshed.merged_at.tzinfo is None else refreshed.merged_at
    assert merged_at == expected_merged
    completed_at = (
        refreshed.completed_at.replace(tzinfo=UTC)
        if refreshed.completed_at and refreshed.completed_at.tzinfo is None
        else refreshed.completed_at
    )
    assert completed_at == expected_merged


def test_completed_at_only_on_verified_merge(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    task = _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.PR_OPENED)

    payload = load_fixture("pull_request_closed_unmerged.json")
    signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-not-merged-001"
    )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status != TaskStatus.MERGED
    assert refreshed.merged_at is None


def test_merge_rate_and_mttr_update_after_merge(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="metrics-pr-002",
            github_repository="owner/superset",
            github_issue_number=100,
            github_issue_url="https://github.com/owner/superset/issues/100",
            issue_title="Metrics PR test 2",
        )
    )
    started = datetime(2026, 3, 13, 11, 0, tzinfo=UTC)
    repo.update_task(task, pr_url=pr_url, status=TaskStatus.READY_FOR_REVIEW, started_at=started)

    payload = load_fixture("pull_request_closed_merged.json")
    with patch("app.api.webhooks._post_merge_actions_background", new=AsyncMock()):
        signed_pr_webhook_request(
            client, payload, webhook_secret, delivery_id="pr-metrics-002"
        )

    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status == TaskStatus.MERGED

    metrics = MetricsService(db_session).compute()
    assert metrics.merge_rate > 0
    assert metrics.median_mttr_seconds == 3600.0


def test_duplicate_pr_webhook_is_idempotent(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.READY_FOR_REVIEW)

    payload = load_fixture("pull_request_closed_merged.json")
    with patch("app.api.webhooks._post_merge_actions_background", new=AsyncMock()):
        response1 = signed_pr_webhook_request(
            client, payload, webhook_secret, delivery_id="pr-dup-001"
        )
        response2 = signed_pr_webhook_request(
            client, payload, webhook_secret, delivery_id="pr-dup-001"
        )

    assert response1.json()["outcome"] == "merged"
    assert response2.json()["outcome"] == "duplicate"


def test_terminal_task_does_not_regress(client, webhook_secret, db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    repo = TaskRepository(db_session)
    task = _create_task_with_pr(db_session, pr_url=pr_url, status=TaskStatus.MERGED)
    merged_at = datetime(2026, 3, 13, 12, 0, tzinfo=UTC)
    repo.update_task(
        task,
        merged_at=merged_at,
        completed_at=merged_at,
    )

    payload = make_pull_request_payload(action="opened")
    response = signed_pr_webhook_request(
        client, payload, webhook_secret, delivery_id="pr-terminal-001"
    )

    assert response.status_code == 200
    refreshed = _refresh_task(db_session, task.id)
    assert refreshed.status == TaskStatus.MERGED


def test_issue_webhook_still_works_after_pr_support(client, webhook_secret):
    payload = make_issue_labeled_payload()
    response = signed_webhook_request(
        client, payload, webhook_secret, delivery_id="issue-after-pr-001"
    )
    assert response.status_code == 202
    assert response.json()["outcome"] == "accepted"
