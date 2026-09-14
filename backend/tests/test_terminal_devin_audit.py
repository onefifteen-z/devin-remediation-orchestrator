from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinSessionResponse
from app.schemas.task import TaskCreate
from app.services.devin import DevinAPIError
from app.services.orchestration import RemediationOrchestrator


class TerminalAuditDevinClient:
    def __init__(self, session: DevinSessionResponse):
        self.session = session
        self.calls = 0

    async def get_session(self, session_id: str) -> DevinSessionResponse:
        self.calls += 1
        assert session_id == self.session.session_id
        return self.session

    async def get_session_consumption(self, session_id, time_after=None, time_before=None):
        from app.schemas.devin_consumption import ConsumptionResponse

        return ConsumptionResponse(total_acus=0.0, consumption_by_date=[])

    async def close(self) -> None:
        return None


def _merged_task_with_stale_devin(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="superset-5",
            github_repository="onefifteen-z/superset",
            github_issue_number=5,
            github_issue_url="https://github.com/onefifteen-z/superset/issues/5",
            issue_title="Helm remediation",
        )
    )
    repo.update_task(
        task,
        status=TaskStatus.MERGED,
        devin_session_id="devin-superset-5",
        devin_session_url="https://app.devin.ai/sessions/devin-superset-5",
        devin_status="running",
        devin_status_detail="waiting_for_user",
        merged_at=datetime(2026, 3, 13, 4, 51, tzinfo=UTC),
        completed_at=datetime(2026, 3, 13, 4, 51, tzinfo=UTC),
    )
    return repo.get_by_id(task.id)


@pytest.mark.asyncio
async def test_sync_terminal_devin_audit_updates_audit_fields_only(db_session):
    task = _merged_task_with_stale_devin(db_session)
    session = DevinSessionResponse(
        session_id="devin-superset-5",
        url="https://app.devin.ai/sessions/devin-superset-5",
        status="suspended",
        status_detail="inactivity",
    )
    settings = Settings(devin_live_enabled=True)
    client = TerminalAuditDevinClient(session)
    orchestrator = RemediationOrchestrator(db_session, settings, devin_client=client)

    updated = await orchestrator.sync_terminal_devin_audit(task.id)

    assert client.calls == 1
    assert updated is not None
    assert updated.status == TaskStatus.MERGED
    assert updated.devin_status == "suspended"
    assert updated.devin_status_detail == "inactivity"
    assert updated.merged_at is not None


@pytest.mark.asyncio
async def test_sync_terminal_devin_audit_skips_non_terminal_tasks(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="active-001",
            github_repository="owner/repo",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/repo/issues/1",
            issue_title="Active task",
        )
    )
    repo.update_task(
        task,
        status=TaskStatus.PR_OPENED,
        devin_session_id="devin-active",
        devin_status="running",
        devin_status_detail="waiting_for_user",
    )

    client = TerminalAuditDevinClient(
        DevinSessionResponse(
            session_id="devin-active",
            url="https://app.devin.ai/sessions/devin-active",
            status="exit",
            status_detail="finished",
        )
    )
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=client
    )

    refreshed = await orchestrator.sync_terminal_devin_audit(task.id)

    assert client.calls == 0
    assert refreshed.devin_status_detail == "waiting_for_user"


@pytest.mark.asyncio
async def test_sync_terminal_devin_audit_preserves_task_on_api_error(db_session):
    task = _merged_task_with_stale_devin(db_session)

    class FailingClient:
        async def get_session(self, session_id: str):
            raise DevinAPIError("Devin API error: 503", status_code=503)

    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(devin_live_enabled=True),
        devin_client=FailingClient(),
    )

    updated = await orchestrator.sync_terminal_devin_audit(task.id)

    assert updated.devin_status == "running"
    assert updated.devin_status_detail == "waiting_for_user"


@pytest.mark.asyncio
async def test_post_merge_github_actions_runs_terminal_audit_first(db_session):
    task = _merged_task_with_stale_devin(db_session)
    settings = Settings(devin_live_enabled=True, github_token="")
    orchestrator = RemediationOrchestrator(db_session, settings)

    with patch.object(
        orchestrator,
        "sync_terminal_devin_audit",
        new=AsyncMock(return_value=task),
    ) as audit_mock:
        await orchestrator.post_merge_github_actions(task.id)

    audit_mock.assert_awaited_once_with(task.id)

