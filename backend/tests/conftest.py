import json
import os
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEVIN_LIVE_ENABLED", "false")
os.environ.setdefault("DEVIN_SCHEDULED_ENABLED", "false")
os.environ.setdefault("DEVIN_SESSION_POLL_INTERVAL_SECONDS", "0")
os.environ.setdefault("DEVIN_REMEDIATION_PLAYBOOK_ID", "")
os.environ.setdefault("ORCHESTRATOR_PUBLIC_URL", "")
os.environ.setdefault("SCHEDULED_INTAKE_TOKEN", "")
os.environ.setdefault("DEVIN_AUTOMATION_ID", "")

from app.config import get_settings
from sqlalchemy import text

from app.database import Base, get_db, get_engine, get_session_factory, reset_database, run_migrations
from app.main import app
from app.models import RemediationTask, WebhookDelivery  # noqa: F401
from app.utils.security import compute_github_signature

get_settings.cache_clear()
reset_database("sqlite:///:memory:")
run_migrations()


@pytest.fixture(autouse=True)
def reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_db():
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    run_migrations()
    yield


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db():
        db = get_session_factory()()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def webhook_secret() -> str:
    return "test-webhook-secret"


def make_issue_labeled_payload(
    repo: str = "owner/superset",
    issue_number: int = 44176,
    label: str = "devin-remediate",
) -> dict:
    return {
        "action": "labeled",
        "issue": {
            "number": issue_number,
            "title": "MCP: update_chart resets omitted fields",
            "html_url": f"https://github.com/{repo}/issues/{issue_number}",
            "labels": [{"name": label}, {"name": "bug"}],
        },
        "repository": {"full_name": repo},
        "label": {"name": label},
    }


def signed_webhook_request(
    client: TestClient,
    payload: dict,
    secret: str,
    delivery_id: str = "test-delivery-001",
    event: str = "issues",
):
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


def load_fixture(name: str) -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / name
    return json.loads(fixture_path.read_text())


def make_pull_request_payload(
    action: str = "opened",
    repo: str = "owner/superset",
    pr_number: int = 123,
    merged: bool = False,
    merged_at: str | None = None,
) -> dict:
    return {
        "action": action,
        "number": pr_number,
        "pull_request": {
            "number": pr_number,
            "html_url": f"https://github.com/{repo}/pull/{pr_number}",
            "state": "closed" if action == "closed" else "open",
            "merged": merged,
            "merged_at": merged_at,
            "head": {"sha": "abc123def456"},
        },
        "repository": {"full_name": repo},
    }


def signed_pr_webhook_request(
    client: TestClient,
    payload: dict,
    secret: str,
    delivery_id: str = "pr-delivery-001",
):
    return signed_webhook_request(
        client,
        payload,
        secret,
        delivery_id=delivery_id,
        event="pull_request",
    )


def make_check_run_payload(
    conclusion: str = "failure",
    check_name: str = "Python Unit Tests",
    repo: str = "owner/superset",
    pr_number: int = 123,
    check_run_id: int = 987654321,
    status: str = "completed",
    output_title: str | None = None,
    output_summary: str | None = None,
    pull_requests: list[dict] | None = None,
) -> dict:
    if pull_requests is None:
        pull_requests = [
            {
                "number": pr_number,
                "head": {"ref": "fix-branch", "sha": "abc123def456"},
                "base": {"ref": "master"},
            }
        ]
    return {
        "action": "completed",
        "check_run": {
            "id": check_run_id,
            "name": check_name,
            "status": status,
            "conclusion": conclusion,
            "html_url": f"https://github.com/{repo}/runs/{check_run_id}",
            "head_sha": "abc123def456",
            "output": {
                "title": output_title or f"{check_name} {conclusion}",
                "summary": output_summary or "",
            },
            "pull_requests": pull_requests,
        },
        "repository": {"full_name": repo},
    }


def signed_check_run_webhook_request(
    client: TestClient,
    payload: dict,
    secret: str,
    delivery_id: str = "check-run-delivery-001",
):
    return signed_webhook_request(
        client,
        payload,
        secret,
        delivery_id=delivery_id,
        event="check_run",
    )
