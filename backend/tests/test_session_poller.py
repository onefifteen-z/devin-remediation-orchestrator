from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.database import get_session_factory
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinPullRequest, DevinSessionResponse
from app.schemas.task import TaskCreate
from app.services.devin import DevinAPIError
from app.services.orchestration import RemediationOrchestrator
from app.workers.poller import SessionPoller


def _make_task(db_session, status: TaskStatus, session_id: str = "devin-test-001"):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=f"poll-{status.value}-{session_id}",
            github_repository="owner/superset",
            github_issue_number=200,
            github_issue_url="https://github.com/owner/superset/issues/200",
            issue_title="Poll test",
        )
    )
    return repo.update_status(
        task,
        status,
        devin_session_id=session_id,
        devin_session_url=f"https://app.devin.ai/sessions/{session_id}",
    )


class FakeDevinClient:
    def __init__(self, session: DevinSessionResponse | None = None, *, fail: bool = False):
        self.session = session
        self.fail = fail
        self.calls: list[str] = []

    async def get_session(self, devin_id: str) -> DevinSessionResponse:
        self.calls.append(devin_id)
        if self.fail:
            raise DevinAPIError("Devin API error: 500", status_code=500)
        if self.session is None:
            return DevinSessionResponse(
                session_id=devin_id,
                url=f"https://app.devin.ai/sessions/{devin_id}",
                status="running",
            )
        return self.session

    async def close(self):
        return None


@pytest.fixture
def poll_settings():
    return Settings(
        devin_session_poll_interval_seconds=15,
        devin_poll_max_failures=3,
    )


@pytest.mark.asyncio
async def test_poll_once_updates_active_task(db_session, poll_settings):
    task = _make_task(db_session, TaskStatus.RUNNING)
    session = DevinSessionResponse(
        session_id=task.devin_session_id,
        url=task.devin_session_url,
        status="running",
        pull_requests=[
            DevinPullRequest(
                pr_url="https://github.com/owner/superset/pull/99",
                pr_state="open",
            )
        ],
        acus_consumed=2.5,
    )
    poller = SessionPoller(
        poll_settings,
        get_session_factory(),
        FakeDevinClient(session),
    )
    await poller.poll_once()

    refreshed = TaskRepository(get_session_factory()()).get_by_id(task.id)
    assert refreshed.pr_url == "https://github.com/owner/superset/pull/99"
    assert refreshed.acu_used == 2.5
    assert refreshed.status == TaskStatus.PR_OPENED


@pytest.mark.asyncio
async def test_poll_once_skips_terminal_tasks(db_session, poll_settings):
    task = _make_task(db_session, TaskStatus.MERGED)
    client = FakeDevinClient()
    poller = SessionPoller(poll_settings, get_session_factory(), client)
    await poller.poll_once()
    assert client.calls == []


@pytest.mark.asyncio
async def test_poll_once_skips_ready_for_review_devin_sync(db_session, poll_settings):
    _make_task(db_session, TaskStatus.READY_FOR_REVIEW)
    client = FakeDevinClient()
    poller = SessionPoller(poll_settings, get_session_factory(), client)
    await poller.poll_once()
    assert client.calls == []


@pytest.mark.asyncio
async def test_poll_once_syncs_ci_for_ready_for_review(db_session, poll_settings):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="poll-ci-ready",
            github_repository="onefifteen-z/superset",
            github_issue_number=10,
            github_issue_url="https://github.com/onefifteen-z/superset/issues/10",
            issue_title="CI pending",
        )
    )
    repo.update_task(
        task,
        status=TaskStatus.READY_FOR_REVIEW,
        pr_url="https://github.com/onefifteen-z/superset/pull/10",
        pr_state="open",
        devin_session_id="devin-ready",
        devin_session_url="https://app.devin.ai/sessions/devin-ready",
    )

    settings = Settings(
        devin_session_poll_interval_seconds=15,
        devin_poll_max_failures=3,
        github_token="ghp_test",
    )
    poller = SessionPoller(settings, get_session_factory(), FakeDevinClient())
    with patch.object(
        RemediationOrchestrator,
        "sync_task_ci_from_github",
        new=AsyncMock(),
    ) as ci_sync_mock:
        await poller.poll_once()

    ci_sync_mock.assert_awaited_once_with(task.id)


@pytest.mark.asyncio
async def test_poll_failure_does_not_change_task_state(db_session, poll_settings):
    task = _make_task(db_session, TaskStatus.RUNNING)
    poller = SessionPoller(
        poll_settings,
        get_session_factory(),
        FakeDevinClient(fail=True),
    )
    await poller.poll_once()

    refreshed = TaskRepository(get_session_factory()()).get_by_id(task.id)
    assert refreshed.status == TaskStatus.RUNNING
    assert poller._failure_counts[task.id] == 1


@pytest.mark.asyncio
async def test_poll_failure_escalates_after_max_failures(db_session, poll_settings):
    task = _make_task(db_session, TaskStatus.RUNNING)
    poller = SessionPoller(
        poll_settings,
        get_session_factory(),
        FakeDevinClient(fail=True),
    )
    for _ in range(3):
        await poller.poll_once()

    refreshed = TaskRepository(get_session_factory()()).get_by_id(task.id)
    assert refreshed.status == TaskStatus.ESCALATED
    assert "poll failures" in (refreshed.escalation_reason or "")


@pytest.mark.asyncio
async def test_poll_once_idempotent_status(db_session, poll_settings):
    task = _make_task(db_session, TaskStatus.RUNNING)
    session = DevinSessionResponse(
        session_id=task.devin_session_id,
        url=task.devin_session_url,
        status="running",
        acus_consumed=1.0,
    )
    client = FakeDevinClient(session)
    poller = SessionPoller(poll_settings, get_session_factory(), client)

    await poller.poll_once()
    await poller.poll_once()

    refreshed = TaskRepository(get_session_factory()()).get_by_id(task.id)
    assert refreshed.status == TaskStatus.RUNNING
    assert refreshed.acu_used == 1.0
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_apply_session_update_persists_acu(db_session):
    task = _make_task(db_session, TaskStatus.RUNNING)
    orchestrator = RemediationOrchestrator(db_session, Settings(), devin_client=FakeDevinClient())
    updated = await orchestrator.apply_session_update(
        task,
        DevinSessionResponse(
            session_id=task.devin_session_id,
            url=task.devin_session_url,
            status="running",
            acus_consumed=4.2,
        ),
    )
    assert updated.acu_used == 4.2
