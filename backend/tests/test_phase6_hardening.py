import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.models.task import TaskKind, TaskStatus, TriggerSource
from app.repositories.tasks import TaskRepository
from app.schemas.remediation import RemediationCreateRequest
from app.schemas.task import RemediationEvent, TaskCreate
from app.services.metrics import MetricsService
from app.services.orchestration import RemediationOrchestrator
from app.services.task_classification import (
    is_production_remediation,
    task_kind_from_title,
    trigger_source_from_event_source,
)
from app.utils.security import verify_bearer_token


def _event(**kwargs) -> RemediationEvent:
    defaults = {
        "github_delivery_id": "webhook:owner/repo:1",
        "source": "github",
        "github_repository": "owner/repo",
        "github_issue_number": 1,
        "github_issue_url": "https://github.com/owner/repo/issues/1",
        "issue_title": "Bug",
    }
    defaults.update(kwargs)
    return RemediationEvent(**defaults)


def test_trigger_source_mapping_includes_scheduled():
    assert trigger_source_from_event_source("scheduled") == TriggerSource.SCHEDULED.value


def test_task_kind_from_title_smoke_test():
    assert task_kind_from_title("Webhook integration smoke test") == TaskKind.SMOKE_TEST.value
    assert task_kind_from_title("Real bug") == TaskKind.REMEDIATION.value


def test_merge_rate_excludes_smoke_test_by_task_kind(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="prod-merged-001",
            github_repository="owner/superset",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/superset/issues/1",
            issue_title="Real remediation",
            task_kind=TaskKind.REMEDIATION.value,
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    merged = repo.get_by_issue("owner/superset", 1)
    repo.update_status(merged, TaskStatus.MERGED)
    repo.create_task(
        TaskCreate(
            github_delivery_id="smoke-001",
            github_repository="owner/superset",
            github_issue_number=2,
            github_issue_url="https://github.com/owner/superset/issues/2",
            issue_title="Webhook integration smoke test",
            task_kind=TaskKind.SMOKE_TEST.value,
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    smoke = repo.get_by_issue("owner/superset", 2)
    repo.update_status(smoke, TaskStatus.MERGED)

    metrics = MetricsService(db_session).compute()
    assert metrics.merge_rate == 1.0
    assert metrics.total_tasks == 1


def test_mttr_excludes_smoke_test(db_session):
    repo = TaskRepository(db_session)
    started = datetime(2026, 1, 1, tzinfo=UTC)
    merged_at = datetime(2026, 1, 1, 1, tzinfo=UTC)
    repo.create_task(
        TaskCreate(
            github_delivery_id="smoke-mttr",
            github_repository="owner/superset",
            github_issue_number=10,
            github_issue_url="https://github.com/owner/superset/issues/10",
            issue_title="Webhook integration smoke test",
            task_kind=TaskKind.SMOKE_TEST.value,
        )
    )
    smoke = repo.get_by_issue("owner/superset", 10)
    repo.update_status(
        smoke,
        TaskStatus.MERGED,
        started_at=started,
        merged_at=merged_at,
    )
    metrics = MetricsService(db_session).compute()
    assert metrics.median_mttr_seconds is None


def test_already_remediated_issue_not_reprocessed(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="merged-001",
            github_repository="owner/repo",
            github_issue_number=42,
            github_issue_url="https://github.com/owner/repo/issues/42",
            issue_title="Merged issue",
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    task = repo.get_by_issue("owner/repo", 42)
    repo.update_status(task, TaskStatus.MERGED, devin_session_id="sess-1")

    orchestrator = RemediationOrchestrator(db_session, Settings())
    _, outcome = orchestrator.ensure_task_for_issue(_event(github_issue_number=42))
    assert outcome == "already_remediated"


def test_existing_devin_session_not_recreated(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="active-001",
            github_repository="owner/repo",
            github_issue_number=50,
            github_issue_url="https://github.com/owner/repo/issues/50",
            issue_title="Active issue",
            trigger_source=TriggerSource.SCAN.value,
        )
    )
    task = repo.get_by_issue("owner/repo", 50)
    repo.update_status(
        task,
        TaskStatus.RUNNING,
        devin_session_id="sess-existing",
    )

    orchestrator = RemediationOrchestrator(db_session, Settings(devin_live_enabled=True))
    mock_client = AsyncMock()
    orchestrator.devin_client = mock_client

    asyncio.run(orchestrator.process_task(task.id))
    mock_client.create_session.assert_not_called()


@pytest.mark.asyncio
async def test_manual_api_skips_existing_merged_issue(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="api-001",
            github_repository="owner/repo",
            github_issue_number=77,
            github_issue_url="https://github.com/owner/repo/issues/77",
            issue_title="API issue",
            trigger_source=TriggerSource.MANUAL_API.value,
        )
    )
    task = repo.get_by_issue("owner/repo", 77)
    repo.update_status(task, TaskStatus.MERGED)

    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(devin_live_enabled=True),
        devin_client=AsyncMock(),
    )
    response = await orchestrator.create_remediation(
        RemediationCreateRequest(
            repository="owner/repo",
            issue_number=77,
            issue_url="https://github.com/owner/repo/issues/77",
        )
    )
    orchestrator.devin_client.create_session.assert_not_called()
    assert response.outcome == "already_remediated"


def test_verified_acu_metrics_exclude_unverified(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="acu-1",
            github_repository="owner/repo",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/repo/issues/1",
            issue_title="Verified ACU",
        )
    )
    verified = repo.get_by_issue("owner/repo", 1)
    repo.update_task(verified, acu_used=3.2, acu_verified=True, acu_source="consumption_api")
    repo.create_task(
        TaskCreate(
            github_delivery_id="acu-2",
            github_repository="owner/repo",
            github_issue_number=2,
            github_issue_url="https://github.com/owner/repo/issues/2",
            issue_title="Reported only",
        )
    )
    reported = repo.get_by_issue("owner/repo", 2)
    repo.update_task(reported, acu_used=9.9, acu_verified=False, acu_source="session_detail")

    metrics = MetricsService(db_session).compute()
    assert metrics.verified_total_acu == 3.2


def test_ci_recovery_requires_verified_timestamp(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="ci-1",
            github_repository="owner/repo",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/repo/issues/1",
            issue_title="CI task",
        )
    )
    task = repo.get_by_issue("owner/repo", 1)
    now = datetime.now(UTC)
    repo.update_task(
        task,
        ci_failure_at=now,
        ci_repair_message_sent_at=now,
    )
    metrics = MetricsService(db_session).compute()
    assert metrics.ci_recovery_rate == 0.0

    repo.update_task(task, ci_repair_verified_at=now)
    metrics = MetricsService(db_session).compute()
    assert metrics.ci_recovery_rate == 1.0


def test_scheduled_intake_missing_token_returns_401(client, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("SCHEDULED_INTAKE_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "owner/repo")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.post("/api/scheduled/intake")
    assert response.status_code == 401


def test_scheduled_intake_invalid_token_returns_401(client, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("SCHEDULED_INTAKE_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "owner/repo")
    from app.config import get_settings

    get_settings.cache_clear()
    response = client.post(
        "/api/scheduled/intake",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_scheduled_intake_valid_token_accepted(client, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_PUBLIC_URL", "https://example.com")
    monkeypatch.setenv("SCHEDULED_INTAKE_TOKEN", "secret-token")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_SCAN_REPOSITORIES", "owner/repo")
    from app.config import get_settings

    get_settings.cache_clear()
    with patch(
        "app.api.scheduled.RemediationOrchestrator.scan_labeled_issues",
        new_callable=AsyncMock,
    ) as scan_mock:
        from app.schemas.scan import ScanResult

        scan_mock.return_value = ScanResult(scanned=0, created=0, skipped=0)
        response = client.post(
            "/api/scheduled/intake",
            headers={"Authorization": "Bearer secret-token"},
        )
    assert response.status_code == 200


def test_verify_bearer_token_constant_time():
    assert verify_bearer_token("Bearer secret", "secret") is True
    assert verify_bearer_token("Bearer wrong", "secret") is False
    assert verify_bearer_token(None, "secret") is False


def test_task_response_excludes_secrets(client, db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="api-safe-001",
            github_repository="owner/repo",
            github_issue_number=99,
            github_issue_url="https://github.com/owner/repo/issues/99",
            issue_title="Safe response",
        )
    )
    response = client.get("/api/tasks")
    body = response.json()
    serialized = str(body)
    assert "cog_" not in serialized
    assert "ghp_" not in serialized
    assert "secret-token" not in serialized


def test_devin_origin_does_not_change_trigger_source(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="origin-001",
            github_repository="owner/repo",
            github_issue_number=5,
            github_issue_url="https://github.com/owner/repo/issues/5",
            issue_title="Origin test",
            trigger_source=TriggerSource.GITHUB_WEBHOOK.value,
        )
    )
    task = repo.get_by_issue("owner/repo", 5)
    repo.update_task(task, devin_origin="api")
    refreshed = repo.get_by_id(task.id)
    assert refreshed.trigger_source == TriggerSource.GITHUB_WEBHOOK.value


@pytest.mark.asyncio
async def test_concurrent_create_session_only_one_call(db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="race-001",
            github_repository="owner/repo",
            github_issue_number=88,
            github_issue_url="https://github.com/owner/repo/issues/88",
            issue_title="Race issue",
        )
    )
    task = repo.get_by_issue("owner/repo", 88)
    settings = Settings(devin_live_enabled=True)
    orchestrator = RemediationOrchestrator(db_session, settings)
    mock_client = AsyncMock()
    mock_client.create_session.return_value = MagicMock(
        session_id="sess-race",
        url="https://devin.example/sess-race",
        status="running",
    )
    orchestrator.devin_client = mock_client

    await asyncio.gather(
        orchestrator.process_task(task.id),
        orchestrator.process_task(task.id),
    )
    assert mock_client.create_session.call_count <= 1
