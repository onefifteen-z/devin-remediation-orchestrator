import json

import pytest

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_insights import parse_session_insights_list
from app.schemas.task import TaskCreate
from app.services.devin import DevinAPIError
from app.services.orchestration import RemediationOrchestrator

RICH_INSIGHTS = {
    "session_id": "devin-rich",
    "session_size": "s",
    "num_user_messages": 1,
    "num_devin_messages": 3,
    "analysis_status": "completed",
    "analysis": {
        "issues": [
            {
                "id": "1",
                "title": "Helm tooling not pre-installed",
                "issue": "Devin had to install helm manually.",
                "impact": "low",
                "label": "Environment issue",
            }
        ],
        "timeline": [
            {
                "title": "PR merged successfully",
                "description": "PR was merged without user intervention.",
                "color": "#34D399",
                "issue_id": None,
            }
        ],
        "action_items": [
            {
                "action_item": "Pre-install helm in the environment blueprint.",
                "type": "machine_setup",
                "issue_id": "1",
            }
        ],
        "classification": {
            "category": "feature_development",
            "confidence": 0.95,
            "programming_languages": ["YAML", "Python"],
            "tools_and_frameworks": ["Helm"],
        },
    },
}

THIN_INSIGHTS = {
    "session_id": "devin-thin",
    "session_size": "xs",
    "num_user_messages": 1,
    "num_devin_messages": 2,
    "analysis_status": "completed",
    "analysis": {
        "issues": [],
        "timeline": [],
        "action_items": [],
        "classification": {
            "category": "data_and_automation",
            "confidence": 0.9,
            "programming_languages": ["Python"],
            "tools_and_frameworks": ["GitHub CLI"],
        },
    },
}


class InsightsDevinClient:
    def __init__(self, items: list[dict] | None = None):
        self.items = items if items is not None else [RICH_INSIGHTS, THIN_INSIGHTS]
        self.calls = 0

    async def list_session_insights(self, limit: int = 100):
        self.calls += 1
        return parse_session_insights_list({"items": self.items})

    async def close(self) -> None:
        return None


def _create_task(db_session, delivery_id: str, issue_number: int, session_id: str | None):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=delivery_id,
            github_repository="owner/repo",
            github_issue_number=issue_number,
            github_issue_url=f"https://github.com/owner/repo/issues/{issue_number}",
            issue_title=f"Task {issue_number}",
        )
    )
    repo.update_task(task, status=TaskStatus.MERGED, devin_session_id=session_id)
    return repo.get_by_id(task.id)


@pytest.mark.asyncio
async def test_sync_session_insights_persists_analysis(db_session):
    task = _create_task(db_session, "rich-001", 1, "devin-rich")
    client = InsightsDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=client
    )

    updated_count = await orchestrator.sync_session_insights()

    assert updated_count == 1
    assert client.calls == 1

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.session_size == "s"
    assert refreshed.num_user_messages == 1
    assert refreshed.num_devin_messages == 3
    assert refreshed.insights_status == "completed"

    analysis = json.loads(refreshed.insights_json)
    assert analysis["classification"]["category"] == "feature_development"
    assert analysis["timeline"][0]["title"] == "PR merged successfully"
    assert analysis["action_items"][0]["type"] == "machine_setup"


@pytest.mark.asyncio
async def test_sync_session_insights_uses_single_batch_call_for_many_tasks(db_session):
    _create_task(db_session, "rich-002", 2, "devin-rich")
    _create_task(db_session, "thin-002", 3, "devin-thin")
    client = InsightsDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=client
    )

    updated_count = await orchestrator.sync_session_insights()

    assert updated_count == 2
    assert client.calls == 1


@pytest.mark.asyncio
async def test_sync_session_insights_keeps_classification_when_no_findings(db_session):
    task = _create_task(db_session, "thin-003", 4, "devin-thin")
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=InsightsDevinClient()
    )

    await orchestrator.sync_session_insights()

    refreshed = TaskRepository(db_session).get_by_id(task.id)
    analysis = json.loads(refreshed.insights_json)
    assert analysis["issues"] == []
    assert analysis["timeline"] == []
    assert analysis["classification"]["category"] == "data_and_automation"


@pytest.mark.asyncio
async def test_sync_session_insights_skips_tasks_without_matching_session(db_session):
    task = _create_task(db_session, "unmatched-004", 5, "devin-unknown")
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=InsightsDevinClient()
    )

    updated_count = await orchestrator.sync_session_insights()

    assert updated_count == 0
    assert TaskRepository(db_session).get_by_id(task.id).session_size is None


@pytest.mark.asyncio
async def test_sync_session_insights_survives_api_error(db_session):
    task = _create_task(db_session, "error-005", 6, "devin-rich")

    class FailingClient:
        async def list_session_insights(self, limit: int = 100):
            raise DevinAPIError("Devin API error: 503", status_code=503)

    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=True), devin_client=FailingClient()
    )

    updated_count = await orchestrator.sync_session_insights()

    assert updated_count == 0
    assert TaskRepository(db_session).get_by_id(task.id).session_size is None


@pytest.mark.asyncio
async def test_sync_session_insights_noop_when_devin_live_disabled(db_session):
    _create_task(db_session, "disabled-006", 7, "devin-rich")
    client = InsightsDevinClient()
    orchestrator = RemediationOrchestrator(
        db_session, Settings(devin_live_enabled=False), devin_client=client
    )

    assert await orchestrator.sync_session_insights() == 0
    assert client.calls == 0
