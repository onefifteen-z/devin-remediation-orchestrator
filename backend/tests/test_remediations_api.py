import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate


@pytest.fixture
def remediation_payload():
    return {
        "repository": "onefifteen-z/superset",
        "issue_number": 1,
        "issue_url": "https://github.com/onefifteen-z/superset/issues/1",
        "issue_type": "mcp-backend",
    }


def test_create_remediation_safe_mode(client, remediation_payload):
    response = client.post("/api/remediations", json=remediation_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "created"
    assert data["devin_live_enabled"] is False
    assert "disabled" in data["message"].lower()
    assert data["task"]["status"] == TaskStatus.RECEIVED.value
    assert data["task"]["github_repository"] == "onefifteen-z/superset"
    assert data["task"]["github_issue_number"] == 1
    assert data["task"]["devin_session_id"] is None


def test_create_remediation_duplicate_issue(client, remediation_payload, db_session):
    TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="api:onefifteen-z/superset:1",
            github_repository="onefifteen-z/superset",
            github_issue_number=1,
            github_issue_url="https://github.com/onefifteen-z/superset/issues/1",
            issue_title="Issue #1",
            issue_type="mcp-backend",
        )
    )

    response = client.post("/api/remediations", json=remediation_payload)

    assert response.status_code == 200
    data = response.json()
    assert data["outcome"] == "skipped"


@pytest.mark.asyncio
@respx.mock
async def test_create_remediation_live_mode(client, db_session, monkeypatch):
    monkeypatch.setenv("DEVIN_LIVE_ENABLED", "true")
    get_settings.cache_clear()

    settings = Settings(
        github_webhook_secret="test",
        devin_live_enabled=True,
        devin_api_key="cog_test_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )

    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "devin-live-001",
                "url": "https://app.devin.ai/sessions/devin-live-001",
                "status": "running",
            },
        )
    )

    def override_get_settings():
        return settings

    from app.database import get_db

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/remediations",
                json={
                    "repository": "owner/superset",
                    "issue_number": 99,
                    "issue_url": "https://github.com/owner/superset/issues/99",
                    "issue_type": "mcp-backend",
                },
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 200
    data = response.json()
    assert data["devin_live_enabled"] is True
    assert data["task"]["devin_session_id"] == "devin-live-001"
    assert data["task"]["devin_session_url"] == "https://app.devin.ai/sessions/devin-live-001"
    assert data["task"]["status"] == TaskStatus.RUNNING.value


@pytest.mark.asyncio
@respx.mock
async def test_create_remediation_devin_auth_error_no_credential_leak(db_session, monkeypatch):
    monkeypatch.setenv("DEVIN_LIVE_ENABLED", "true")
    get_settings.cache_clear()

    settings = Settings(
        github_webhook_secret="test",
        devin_live_enabled=True,
        devin_api_key="cog_super_secret_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )

    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )

    from app.database import get_db

    def override_get_db():
        yield db_session

    def override_get_settings():
        return settings

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/remediations",
                json={
                    "repository": "owner/superset",
                    "issue_number": 50,
                    "issue_url": "https://github.com/owner/superset/issues/50",
                    "issue_type": "mcp-backend",
                },
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 502
    assert "cog_super_secret_key" not in response.text


@pytest.mark.asyncio
@respx.mock
async def test_create_remediation_devin_server_error_returns_503(db_session, monkeypatch):
    monkeypatch.setenv("DEVIN_LIVE_ENABLED", "true")
    get_settings.cache_clear()

    settings = Settings(
        github_webhook_secret="test",
        devin_live_enabled=True,
        devin_api_key="cog_test_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )

    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(500, json={"detail": "Server error"})
    )

    from app.database import get_db

    def override_get_db():
        yield db_session

    def override_get_settings():
        return settings

    app.dependency_overrides[get_settings] = override_get_settings
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/remediations",
                json={
                    "repository": "owner/superset",
                    "issue_number": 51,
                    "issue_url": "https://github.com/owner/superset/issues/51",
                    "issue_type": "mcp-backend",
                },
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert response.status_code == 503
    assert "cog_test_key" not in response.text
