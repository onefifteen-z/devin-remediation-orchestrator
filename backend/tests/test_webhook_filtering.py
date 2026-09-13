import json

from app.utils.security import compute_github_signature
from tests.conftest import make_issue_labeled_payload


def _post(client, payload, event, delivery_id, secret):
    body = json.dumps(payload).encode()
    signature = compute_github_signature(body, secret)
    return client.post(
        "/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": event,
            "X-GitHub-Delivery": delivery_id,
            "X-Hub-Signature-256": signature,
        },
    )


def test_irrelevant_event_ignored(client, webhook_secret):
    payload = {"action": "opened", "repository": {"full_name": "owner/repo"}}
    response = _post(client, payload, "push", "delivery-push-001", webhook_secret)
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


def test_issue_without_remediate_label_ignored(client, webhook_secret):
    payload = make_issue_labeled_payload(label="bug")
    response = _post(client, payload, "issues", "delivery-no-label-001", webhook_secret)
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


def test_correct_labeled_issue_accepted(client, webhook_secret):
    payload = make_issue_labeled_payload()
    response = _post(client, payload, "issues", "delivery-accepted-001", webhook_secret)
    assert response.status_code == 202
    data = response.json()
    assert data["outcome"] == "accepted"
    assert "task_id" in data

    tasks = client.get("/api/tasks").json()
    assert tasks["total"] == 1
    assert tasks["items"][0]["github_issue_number"] == 44176
    assert tasks["items"][0]["status"] == "RECEIVED"


def test_issues_opened_ignored(client, webhook_secret):
    payload = {
        "action": "opened",
        "issue": {
            "number": 1,
            "title": "Opened issue",
            "html_url": "https://github.com/owner/repo/issues/1",
            "labels": [],
        },
        "repository": {"full_name": "owner/repo"},
    }
    response = _post(client, payload, "issues", "delivery-opened-001", webhook_secret)
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"
