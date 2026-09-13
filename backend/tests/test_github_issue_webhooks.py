import json
from unittest.mock import AsyncMock, patch

from app.schemas.github_events import normalize_issue_event
from tests.conftest import make_issue_labeled_payload, signed_webhook_request


def test_normalized_issue_event_includes_body_and_source():
    payload = make_issue_labeled_payload()
    payload["issue"]["body"] = "Steps to reproduce the bug"
    event_fields = normalize_issue_event("delivery-normalize-001", payload)

    assert event_fields["source"] == "github"
    assert event_fields["issue_title"] == "MCP: update_chart resets omitted fields"
    assert event_fields["issue_body"] == "Steps to reproduce the bug"
    assert event_fields["issue_type"] == "bug"
    assert event_fields["action"] == "labeled"


def test_issues_opened_ignored(client, webhook_secret):
    payload = {
        "action": "opened",
        "issue": {
            "number": 1,
            "title": "New issue",
            "html_url": "https://github.com/owner/superset/issues/1",
            "labels": [],
        },
        "repository": {"full_name": "owner/superset"},
    }
    response = signed_webhook_request(
        client, payload, webhook_secret, delivery_id="issue-opened-001"
    )
    assert response.status_code == 200
    assert response.json()["outcome"] == "ignored"


def test_live_mode_invokes_orchestrator_path(client, webhook_secret):
    payload = make_issue_labeled_payload()
    with patch("app.api.webhooks._process_task_background", new=AsyncMock()) as mock_process:
        response = signed_webhook_request(
            client, payload, webhook_secret, delivery_id="issue-live-path-001"
        )

    assert response.status_code == 202
    mock_process.assert_called_once()


def test_safe_mode_does_not_call_devin(client, webhook_secret):
    payload = make_issue_labeled_payload()
    with patch("app.services.devin.DevinClient.create_session", new=AsyncMock()) as mock_create:
        response = signed_webhook_request(
            client, payload, webhook_secret, delivery_id="issue-safe-mode-001"
        )

    assert response.status_code == 202
    mock_create.assert_not_called()


def test_duplicate_delivery_does_not_create_duplicate_devin_session(client, webhook_secret):
    payload = make_issue_labeled_payload()
    with patch("app.api.webhooks._process_task_background", new=AsyncMock()) as mock_process:
        response1 = signed_webhook_request(
            client, payload, webhook_secret, delivery_id="issue-dedup-devin-001"
        )
        response2 = signed_webhook_request(
            client, payload, webhook_secret, delivery_id="issue-dedup-devin-001"
        )

    assert response1.json()["outcome"] == "accepted"
    assert response2.json()["outcome"] == "duplicate"
    mock_process.assert_called_once()
