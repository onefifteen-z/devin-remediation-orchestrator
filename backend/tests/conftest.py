import json
import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("GITHUB_WEBHOOK_SECRET", "test-webhook-secret")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DEVIN_LIVE_ENABLED", "false")

from app.config import get_settings
from app.database import Base, get_db, get_engine, get_session_factory, reset_database
from app.main import app
from app.utils.security import compute_github_signature

get_settings.cache_clear()
reset_database("sqlite:///:memory:")
Base.metadata.create_all(bind=get_engine())


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=get_engine())
    Base.metadata.create_all(bind=get_engine())
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
