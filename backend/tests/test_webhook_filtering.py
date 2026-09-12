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
    assert response.json()["status"] == "ignored"


def test_issue_without_remediate_label_ignored(client, webhook_secret):
    payload = make_issue_labeled_payload(label="bug")
    response = _post(client, payload, "issues", "delivery-no-label-001", webhook_secret)
    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_correct_labeled_issue_accepted(client, webhook_secret):
    payload = make_issue_labeled_payload()
    response = _post(client, payload, "issues", "delivery-accepted-001", webhook_secret)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["task"]["github_issue_number"] == 44176
    assert data["task"]["status"] == "RECEIVED"
