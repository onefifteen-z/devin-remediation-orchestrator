import pytest
from unittest.mock import AsyncMock

from app.config import Settings
from app.repositories.tasks import TaskRepository
from app.services.github import GitHubClient
from app.services.orchestration import RemediationOrchestrator


@pytest.fixture
def scan_settings():
    return Settings(
        github_token="ghp_test",
        github_scan_repositories="owner/superset",
        remediate_label="devin-remediate",
        devin_live_enabled=False,
    )


@pytest.mark.asyncio
async def test_scan_creates_only_new_issues(db_session, scan_settings):
    mock_github = AsyncMock(spec=GitHubClient)
    mock_github.list_issues_by_label.return_value = [
        {
            "repository": "owner/superset",
            "number": 100,
            "title": "Issue 100",
            "html_url": "https://github.com/owner/superset/issues/100",
            "labels": [{"name": "devin-remediate"}, {"name": "bug"}],
        },
        {
            "repository": "owner/superset",
            "number": 101,
            "title": "Issue 101",
            "html_url": "https://github.com/owner/superset/issues/101",
            "labels": [{"name": "devin-remediate"}],
        },
    ]

    orchestrator = RemediationOrchestrator(db_session, scan_settings, github_client=mock_github)
    result = await orchestrator.scan_labeled_issues()

    assert result.scanned == 2
    assert result.created == 2
    assert result.skipped == 0
    assert len(result.created_task_ids) == 2
    mock_github.list_issues_by_label.assert_awaited_with(
        "owner/superset",
        "devin-remediate",
    )


@pytest.mark.asyncio
async def test_scan_skips_existing_issues(db_session, scan_settings):
    mock_github = AsyncMock(spec=GitHubClient)
    mock_github.list_issues_by_label.return_value = [
        {
            "repository": "owner/superset",
            "number": 200,
            "title": "Issue 200",
            "html_url": "https://github.com/owner/superset/issues/200",
            "labels": [{"name": "devin-remediate"}],
        }
    ]

    orchestrator = RemediationOrchestrator(db_session, scan_settings, github_client=mock_github)
    first = await orchestrator.scan_labeled_issues()
    second = await orchestrator.scan_labeled_issues()

    assert first.created == 1
    assert second.scanned == 1
    assert second.created == 0
    assert second.skipped == 1
    assert second.skipped_issues == ["owner/superset#200"]

    repo = TaskRepository(db_session)
    assert repo.get_by_issue("owner/superset", 200) is not None


def test_scan_endpoint_requires_token(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.post("/api/scan/github")
    assert response.status_code == 503


def test_scan_endpoint_requires_repositories(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "")
    from app.config import get_settings

    get_settings.cache_clear()

    response = client.post("/api/scan/github")
    assert response.status_code == 400
