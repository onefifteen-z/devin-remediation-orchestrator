from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from app.config import Settings, get_settings
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.scheduled import ScheduledRemediationService, build_schedule_prompt


def test_scheduling_disabled_by_default():
    settings = Settings()
    assert settings.devin_scheduled_enabled is False


def test_schedule_prompt_includes_intake_url():
    settings = Settings(
        orchestrator_public_url="https://orchestrator.example.com",
        scheduled_intake_token="secret-token",
        scheduled_label="devin-scheduled",
    )
    prompt = build_schedule_prompt(settings)
    assert "https://orchestrator.example.com/api/scheduled/intake" in prompt
    assert "devin-scheduled" in prompt
    assert "secret-token" in prompt
    assert "Do not modify repository code" in prompt


@pytest.mark.asyncio
@respx.mock
async def test_configured_schedule_payload_is_correct():
    settings = Settings(
        devin_api_key="cog_test",
        devin_org_id="org-test",
        devin_api_base_url="https://api.devin.ai/v3",
        devin_scheduled_enabled=True,
        orchestrator_public_url="https://orchestrator.example.com",
        devin_schedule_cron="0 9 * * 1-5",
        devin_remediation_playbook_id="playbook-001",
    )
    route = respx.post("https://api.devin.ai/v3/organizations/org-test/schedules").mock(
        return_value=httpx.Response(
            200,
            json={
                "schedule_id": "sched-001",
                "title": "Remediation intake triage",
                "prompt": "test",
                "schedule_type": "recurring",
                "frequency": "0 9 * * 1-5",
                "enabled": True,
            },
        )
    )
    from app.services.devin import DevinClient

    service = ScheduledRemediationService(settings, DevinClient(settings))
    schedule_id = await service.ensure_schedule()
    await service.devin_client.close()
    assert schedule_id == "sched-001"
    body = route.calls.last.request.content.decode()
    assert "recurring" in body
    assert "0 9 * * 1-5" in body
    assert "playbook-001" in body


@pytest.mark.asyncio
async def test_no_live_schedule_created_in_tests(monkeypatch):
    monkeypatch.setenv("DEVIN_SCHEDULED_ENABLED", "false")
    get_settings.cache_clear()
    settings = get_settings()
    from app.services.devin import DevinClient

    service = ScheduledRemediationService(settings, DevinClient(settings))
    assert await service.ensure_schedule() is None
    await service.devin_client.close()


@pytest.mark.asyncio
async def test_scheduled_intake_skips_duplicate_issue(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "owner/superset")
    get_settings.cache_clear()

    with patch(
        "app.api.scheduled.RemediationOrchestrator.scan_labeled_issues",
        new_callable=AsyncMock,
    ) as scan_mock:
        from app.schemas.scan import ScanResult

        scan_mock.return_value = ScanResult(scanned=1, created=0, skipped=1, skipped_issues=["owner/superset#42"])
        response = client.post("/api/scheduled/intake")
    assert response.status_code == 200
    assert response.json()["skipped"] == 1


@pytest.mark.asyncio
async def test_scheduled_intake_uses_same_orchestration_primitives(client, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "owner/superset")
    get_settings.cache_clear()

    with patch(
        "app.api.scheduled.RemediationOrchestrator.scan_labeled_issues",
        new_callable=AsyncMock,
    ) as scan_mock:
        from app.schemas.scan import ScanResult

        scan_mock.return_value = ScanResult(scanned=2, created=1, skipped=1, created_task_ids=[1])
        with patch("app.api.scheduled._process_task_background") as process_mock:
            response = client.post("/api/scheduled/intake")
    assert response.status_code == 200
    scan_mock.assert_awaited_once()
    kwargs = scan_mock.await_args.kwargs
    assert kwargs["source"] == "scheduled"
    assert kwargs["delivery_prefix"] == "scheduled"
    assert kwargs["label"] == "devin-scheduled"
    process_mock.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_scheduled_scan_uses_scheduled_label(db_session):
    from unittest.mock import AsyncMock

    from app.services.github import GitHubClient
    from app.services.orchestration import RemediationOrchestrator

    settings = Settings(
        github_token="ghp_test",
        github_scan_repositories="owner/superset",
        remediate_label="devin-remediate",
        scheduled_label="devin-scheduled",
    )
    mock_github = AsyncMock(spec=GitHubClient)
    mock_github.list_issues_by_label.return_value = [
        {
            "repository": "owner/superset",
            "number": 300,
            "title": "Scheduled issue",
            "html_url": "https://github.com/owner/superset/issues/300",
            "labels": [{"name": "devin-scheduled"}, {"name": "bug"}],
        }
    ]

    orchestrator = RemediationOrchestrator(db_session, settings, github_client=mock_github)
    await orchestrator.scan_labeled_issues(
        source="scheduled",
        delivery_prefix="scheduled",
        run_id="run1",
        label=settings.scheduled_label,
    )

    mock_github.list_issues_by_label.assert_awaited_once_with(
        "owner/superset",
        "devin-scheduled",
    )


def test_existing_merged_remediation_not_recreated(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="scheduled:run1:owner/superset:42",
            github_repository="owner/superset",
            github_issue_number=42,
            github_issue_url="https://github.com/owner/superset/issues/42",
            issue_title="Existing merged",
            trigger_source="scheduled",
        )
    )
    from app.schemas.task import RemediationEvent
    from app.services.orchestration import RemediationOrchestrator

    orchestrator = RemediationOrchestrator(db_session, Settings())
    event = RemediationEvent(
        github_delivery_id="scheduled:run2:owner/superset:42",
        source="scheduled",
        github_repository="owner/superset",
        github_issue_number=42,
        github_issue_url="https://github.com/owner/superset/issues/42",
        issue_title="Existing merged",
    )
    _, outcome = orchestrator.ensure_task_for_issue(event)
    assert outcome == "skipped"


@pytest.mark.asyncio
async def test_schedule_api_error_handled_safely():
    settings = Settings(
        devin_api_key="cog_test",
        devin_org_id="org-test",
        devin_api_base_url="https://api.devin.ai/v3",
        devin_scheduled_enabled=True,
        orchestrator_public_url="https://orchestrator.example.com",
    )

    class FailingScheduleClient:
        async def create_schedule(self, body):
            from app.services.devin import DevinAPIError

            raise DevinAPIError("Devin API error: 500", status_code=500)

        async def update_schedule(self, schedule_id, body):
            from app.services.devin import DevinAPIError

            raise DevinAPIError("Devin API error: 500", status_code=500)

    service = ScheduledRemediationService(settings, FailingScheduleClient())
    assert await service.ensure_schedule() is None
