import json

from tests.conftest import make_issue_labeled_payload


def test_valid_hmac_signature_accepted(client, webhook_secret):
    payload = make_issue_labeled_payload()
    body = json.dumps(payload).encode()
    from app.utils.security import compute_github_signature

    signature = compute_github_signature(body, webhook_secret)
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-valid-001",
            "X-Hub-Signature-256": signature,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_invalid_hmac_signature_rejected(client, webhook_secret):
    payload = make_issue_labeled_payload()
    body = json.dumps(payload).encode()
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Event": "issues",
            "X-GitHub-Delivery": "delivery-invalid-001",
            "X-Hub-Signature-256": "sha256=invalidsignature",
        },
    )
    assert response.status_code == 401
