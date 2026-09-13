from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from tests.conftest import make_issue_labeled_payload, signed_webhook_request


def test_webhook_skips_issue_already_created_by_scan(client, webhook_secret, db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="manual:owner/superset:44176",
            github_repository="owner/superset",
            github_issue_number=44176,
            github_issue_url="https://github.com/owner/superset/issues/44176",
            issue_title="Existing scanned issue",
            issue_type="bug",
        )
    )

    payload = make_issue_labeled_payload()
    response = signed_webhook_request(
        client, payload, webhook_secret, delivery_id="webhook-after-scan-001"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "duplicate"
    assert client.get("/api/tasks").json()["total"] == 1
