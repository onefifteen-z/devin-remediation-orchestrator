import pytest
from datetime import UTC, datetime, timedelta
import asyncio

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import IssueAlreadyTrackedError, TaskRepository
from app.schemas.remediation import RemediationCreateRequest
from app.schemas.task import RemediationEvent, TaskCreate
from app.services.devin import DevinAPIError
from app.services.orchestration import RemediationOrchestrator
from app.services.prompt_builder import build_remediation_prompt, build_session_tags


@pytest.fixture
def settings():
    return Settings(
        github_webhook_secret="test",
        max_active_sessions=2,
        max_retries=3,
        devin_session_timeout_minutes=60,
        devin_live_enabled=False,
    )


@pytest.fixture
def orchestrator(db_session, settings):
    return RemediationOrchestrator(db_session, settings)


def _make_event(delivery_id: str = "orch-delivery-001") -> RemediationEvent:
    return RemediationEvent(
        github_delivery_id=delivery_id,
        github_repository="owner/superset",
        github_issue_number=100,
        github_issue_url="https://github.com/owner/superset/issues/100",
        issue_title="Test issue",
        issue_type="bug",
    )


def test_handle_webhook_event_creates_task(orchestrator):
    task, outcome = orchestrator.handle_webhook_event(_make_event())
    assert outcome == "created"
    assert task.status == TaskStatus.RECEIVED
    assert task.github_repository == "owner/superset"


def test_state_transition(orchestrator, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="transition-001",
            github_repository="owner/superset",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/superset/issues/1",
            issue_title="Transition test",
        )
    )
    updated = orchestrator.transition(
        task,
        TaskStatus.SESSION_CREATED,
        devin_session_id="devin-abc123",
        devin_session_url="https://app.devin.ai/sessions/devin-abc123",
        started_at=datetime.now(UTC),
    )
    assert updated.status == TaskStatus.SESSION_CREATED
    assert updated.devin_session_id == "devin-abc123"


@pytest.mark.asyncio
async def test_process_task_stays_received_when_live_disabled(orchestrator, db_session):
    task, _ = orchestrator.handle_webhook_event(_make_event("process-001"))
    await orchestrator.process_task(task.id)
    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.status == TaskStatus.RECEIVED


def test_increment_retry_escalates_at_max(orchestrator, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="retry-001",
            github_repository="owner/superset",
            github_issue_number=2,
            github_issue_url="https://github.com/owner/superset/issues/2",
            issue_title="Retry test",
            max_retries=2,
        )
    )
    task = orchestrator.increment_retry(task, "API error")
    assert task.retry_count == 1
    assert task.status == TaskStatus.RECEIVED

    task = orchestrator.increment_retry(task, "API error again")
    assert task.status == TaskStatus.ESCALATED
    assert task.retry_count == 2


def test_should_escalate_on_timeout(orchestrator, db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="timeout-001",
            github_repository="owner/superset",
            github_issue_number=3,
            github_issue_url="https://github.com/owner/superset/issues/3",
            issue_title="Timeout test",
        )
    )
    task = repo.update_task(
        task,
        started_at=datetime.now(UTC) - timedelta(minutes=120),
    )
    assert orchestrator.should_escalate(task) is True


def test_concurrency_cap_counted(orchestrator, db_session):
    repo = TaskRepository(db_session)
    for i in range(2):
        task = repo.create_task(
            TaskCreate(
                github_delivery_id=f"active-{i}",
                github_repository="owner/superset",
                github_issue_number=10 + i,
                github_issue_url=f"https://github.com/owner/superset/issues/{10 + i}",
                issue_title=f"Active {i}",
            )
        )
        repo.update_status(task, TaskStatus.RUNNING)
    assert repo.count_active_sessions() == 2


class FakeDevinClient:
    def __init__(self, *, fail: bool = False):
        self.calls = 0
        self.fail = fail
        self.last_prompt = None
        self.last_tags = None
        self.last_repos = None
        self.last_max_acu_limit = None

    async def create_session(self, prompt, tags=None, max_acu_limit=None, repos=None):
        self.calls += 1
        self.last_prompt = prompt
        self.last_tags = tags
        self.last_repos = repos
        self.last_max_acu_limit = max_acu_limit
        await asyncio.sleep(0.05)

        if self.fail:
            raise DevinAPIError("Devin API error: 500", status_code=500)

        class Result:
            session_id = "devin-test-001"
            url = "https://app.devin.ai/sessions/devin-test-001"
            status = "running"

        return Result()


class FailingDevinClient:
    def __init__(self, message: str = "Devin API error: 500"):
        self.calls = 0
        self.message = message

    async def create_session(self, prompt, tags=None, max_acu_limit=None, repos=None):
        self.calls += 1
        raise DevinAPIError(self.message, status_code=500)


@pytest.mark.asyncio
async def test_process_task_claims_atomically(db_session):
    settings = Settings(
        github_webhook_secret="test",
        max_active_sessions=5,
        max_retries=3,
        devin_session_timeout_minutes=60,
        devin_live_enabled=True,
    )
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, settings, devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("atomic-001"))

    await asyncio.gather(
        orchestrator.process_task(task.id),
        orchestrator.process_task(task.id),
    )

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert fake_client.calls == 1
    assert refreshed.status == TaskStatus.RUNNING
    assert refreshed.devin_session_id == "devin-test-001"
    assert refreshed.devin_session_url == "https://app.devin.ai/sessions/devin-test-001"


def test_duplicate_issue_is_skipped(orchestrator):
    _, first_outcome = orchestrator.handle_webhook_event(_make_event("dup-001"))
    task, second_outcome = orchestrator.handle_webhook_event(
        RemediationEvent(
            github_delivery_id="another-delivery-id",
            github_repository="owner/superset",
            github_issue_number=100,
            github_issue_url="https://github.com/owner/superset/issues/100",
            issue_title="Test issue",
            issue_type="bug",
        )
    )
    assert first_outcome == "created"
    assert second_outcome == "skipped"


def test_issue_unique_constraint_enforced(orchestrator, db_session):
    orchestrator.handle_webhook_event(_make_event("unique-001"))
    with pytest.raises(IssueAlreadyTrackedError):
        TaskRepository(db_session).create_task(
            TaskCreate(
                github_delivery_id="manual:owner/superset:100",
                github_repository="owner/superset",
                github_issue_number=100,
                github_issue_url="https://github.com/owner/superset/issues/100",
                issue_title="Duplicate issue",
            )
        )


def _live_settings(**overrides):
    defaults = {
        "github_webhook_secret": "test",
        "max_active_sessions": 5,
        "max_retries": 3,
        "devin_session_timeout_minutes": 60,
        "devin_live_enabled": True,
        "devin_api_key": "cog_test_secret_key",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_process_task_calls_devin_when_live_enabled(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("live-001"))

    await orchestrator.process_task(task.id)

    assert fake_client.calls == 1


@pytest.mark.asyncio
async def test_process_task_includes_repository_in_prompt_and_repos(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("prompt-001"))

    await orchestrator.process_task(task.id)

    assert "owner/superset" in fake_client.last_prompt
    assert "https://github.com/owner/superset/issues/100" in fake_client.last_prompt
    assert fake_client.last_repos == ["owner/superset"]


@pytest.mark.asyncio
async def test_process_task_generates_correct_prompt(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("prompt-002"))

    await orchestrator.process_task(task.id)

    expected_prompt = build_remediation_prompt(task)
    assert fake_client.last_prompt == expected_prompt
    assert "Diagnose the root cause" in fake_client.last_prompt
    assert "smallest safe fix" in fake_client.last_prompt


@pytest.mark.asyncio
async def test_process_task_generates_correct_tags(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("tags-001"))

    await orchestrator.process_task(task.id)

    expected_tags = build_session_tags(task)
    assert fake_client.last_tags == expected_tags
    assert "source=github" in fake_client.last_tags
    assert "workflow=issue-remediation" in fake_client.last_tags
    assert "repo=owner/superset" in fake_client.last_tags
    assert "issue=100" in fake_client.last_tags
    assert "issue-type=bug" in fake_client.last_tags
    assert "environment=take-home" in fake_client.last_tags


@pytest.mark.asyncio
async def test_process_task_persists_session_id_and_url(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("persist-001"))

    await orchestrator.process_task(task.id)

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.devin_session_id == "devin-test-001"
    assert refreshed.devin_session_url == "https://app.devin.ai/sessions/devin-test-001"


@pytest.mark.asyncio
async def test_process_task_status_transitions_received_to_running(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("transition-002"))

    await orchestrator.process_task(task.id)

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.status == TaskStatus.RUNNING
    assert refreshed.started_at is not None


@pytest.mark.asyncio
async def test_process_task_devin_failure_reverts_to_received(db_session):
    failing_client = FailingDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, _live_settings(), devin_client=failing_client
    )
    task, _ = orchestrator.handle_webhook_event(_make_event("fail-001"))

    await orchestrator.process_task(task.id)

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.status == TaskStatus.RECEIVED
    assert refreshed.devin_session_id is None
    assert refreshed.failure_reason is not None
    assert refreshed.retry_count == 1


@pytest.mark.asyncio
async def test_devin_error_does_not_leak_credentials(caplog, db_session):
    failing_client = FailingDevinClient("Devin API error: 500")
    settings = _live_settings(devin_api_key="cog_super_secret_key")
    orchestrator = RemediationOrchestrator(db_session, settings, devin_client=failing_client)
    task, _ = orchestrator.handle_webhook_event(_make_event("leak-001"))

    await orchestrator.process_task(task.id)

    log_text = caplog.text
    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert "cog_super_secret_key" not in log_text
    assert "cog_super_secret_key" not in (refreshed.failure_reason or "")


@pytest.mark.asyncio
async def test_create_remediation_safe_mode(db_session):
    settings = Settings(
        github_webhook_secret="test",
        devin_live_enabled=False,
    )
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, settings, devin_client=fake_client)

    response = await orchestrator.create_remediation(
        RemediationCreateRequest(
            repository="owner/superset",
            issue_number=42,
            issue_url="https://github.com/owner/superset/issues/42",
            issue_type="mcp-backend",
        )
    )

    assert response.outcome == "created"
    assert response.devin_live_enabled is False
    assert "disabled" in response.message.lower()
    assert response.task.status == TaskStatus.RECEIVED
    assert fake_client.calls == 0
