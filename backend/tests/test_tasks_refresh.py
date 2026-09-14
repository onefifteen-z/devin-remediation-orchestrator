from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinSessionResponse
from app.schemas.task import TaskCreate
from app.services.orchestration import RemediationOrchestrator


class RefreshDevinClient:
    def __init__(self):
        self.calls = 0
        self.insights_calls = 0

    async def get_session(self, session_id: str) -> DevinSessionResponse:
        self.calls += 1
        return DevinSessionResponse(
            session_id=session_id,
            url=f"https://app.devin.ai/sessions/{session_id}",
            status="running",
            status_detail="working",
            acus_consumed=0.0,
        )

    async def get_session_consumption(self, session_id, time_after=None, time_before=None):
        from app.schemas.devin_consumption import ConsumptionResponse

        return ConsumptionResponse(total_acus=0.0, consumption_by_date=[])

    async def list_session_insights(self, limit: int = 100):
        from app.schemas.devin_insights import parse_session_insights_list

        self.insights_calls += 1
        return parse_session_insights_list(
            {
                "items": [
                    {
                        "session_id": session_id,
                        "session_size": "s",
                        "num_user_messages": 1,
                        "num_devin_messages": 3,
                        "analysis_status": "completed",
                        "analysis": {"issues": [], "timeline": [], "action_items": []},
                    }
                    for session_id in ("devin-active", "devin-merged")
                ]
            }
        )

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_refresh_tasks_from_devin_syncs_active_tasks(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="refresh-active",
            github_repository="owner/repo",
            github_issue_number=1,
            github_issue_url="https://github.com/owner/repo/issues/1",
            issue_title="Active",
        )
    )
    repo.update_task(
        task,
        status=TaskStatus.RUNNING,
        devin_session_id="devin-active",
        devin_session_url="https://app.devin.ai/sessions/devin-active",
    )

    client = RefreshDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=client
    )
    result = await orchestrator.refresh_tasks_from_devin()

    refreshed = repo.get_by_id(task.id)
    assert result["synced"] == 1
    assert client.calls == 1
    assert refreshed.devin_status_detail == "working"
    assert refreshed.acu_source == "session_detail"
    assert client.insights_calls == 1
    assert refreshed.session_size == "s"
    assert refreshed.num_devin_messages == 3


@pytest.mark.asyncio
async def test_refresh_tasks_from_devin_syncs_terminal_tasks(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="refresh-merged",
            github_repository="owner/repo",
            github_issue_number=2,
            github_issue_url="https://github.com/owner/repo/issues/2",
            issue_title="Merged",
        )
    )
    repo.update_task(
        task,
        status=TaskStatus.MERGED,
        devin_session_id="devin-merged",
        devin_session_url="https://app.devin.ai/sessions/devin-merged",
        devin_status="running",
        devin_status_detail="waiting_for_user",
        merged_at=datetime.now(UTC),
    )

    client = RefreshDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=client
    )
    result = await orchestrator.refresh_tasks_from_devin()

    refreshed = repo.get_by_id(task.id)
    assert result["synced"] == 1
    assert refreshed.devin_status_detail == "working"
    assert refreshed.acu_verified is True
    assert refreshed.acu_source == "consumption_api"


def test_refresh_tasks_api(client, db_session):
    repo = TaskRepository(db_session)
    repo.create_task(
        TaskCreate(
            github_delivery_id="refresh-api",
            github_repository="owner/repo",
            github_issue_number=3,
            github_issue_url="https://github.com/owner/repo/issues/3",
            issue_title="API refresh",
        )
    )

    with patch(
        "app.api.tasks.RemediationOrchestrator.refresh_tasks_from_devin",
        new=AsyncMock(return_value={"synced": 1, "skipped": 0, "errors": 0}),
    ):
        response = client.post("/api/tasks/refresh")

    assert response.status_code == 200
    assert response.json() == {"synced": 1, "skipped": 0, "errors": 0}
