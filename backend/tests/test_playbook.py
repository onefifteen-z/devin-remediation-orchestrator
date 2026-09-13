import pytest

from app.config import Settings
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate, TaskResponse
from app.services.prompt_builder import build_remediation_prompt, build_session_tags
from app.services.orchestration import RemediationOrchestrator
from tests.test_orchestration import FakeDevinClient, _live_settings


@pytest.mark.asyncio
async def test_configured_playbook_is_sent(db_session):
    fake_client = FakeDevinClient()
    settings = _live_settings(devin_remediation_playbook_id="playbook-remediation-001")
    orchestrator = RemediationOrchestrator(db_session, settings, devin_client=fake_client)
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-001",
            github_repository="owner/superset",
            github_issue_number=601,
            github_issue_url="https://github.com/owner/superset/issues/601",
            issue_title="Playbook test",
            trigger_source="manual_api",
        )
    )
    await orchestrator.process_task(task.id)
    assert fake_client.last_playbook_id == "playbook-remediation-001"
    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.playbook_id == "playbook-remediation-001"


@pytest.mark.asyncio
async def test_missing_playbook_falls_back_safely(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-002",
            github_repository="owner/superset",
            github_issue_number=602,
            github_issue_url="https://github.com/owner/superset/issues/602",
            issue_title="No playbook",
        )
    )
    await orchestrator.process_task(task.id)
    assert fake_client.last_playbook_id is None


def test_playbook_prompt_is_concise(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-003",
            github_repository="owner/superset",
            github_issue_number=603,
            github_issue_url="https://github.com/owner/superset/issues/603",
            issue_title="Prompt concise",
            issue_type="bug",
        )
    )
    settings = Settings(devin_remediation_playbook_id="playbook-001")
    prompt = build_remediation_prompt(task, settings)
    assert "configured remediation playbook" in prompt
    assert "Diagnose the root cause" not in prompt
    assert "Do not merge pull requests" in prompt


def test_prompt_without_playbook_keeps_objectives(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-004",
            github_repository="owner/superset",
            github_issue_number=604,
            github_issue_url="https://github.com/owner/superset/issues/604",
            issue_title="Prompt full",
        )
    )
    prompt = build_remediation_prompt(task, Settings())
    assert "Diagnose the root cause" in prompt


def test_playbook_does_not_create_second_orchestration_path(db_session):
    orchestrator = RemediationOrchestrator(db_session, _live_settings())
    assert hasattr(orchestrator, "process_task")
    assert not hasattr(orchestrator, "process_playbook_task")


@pytest.mark.asyncio
async def test_ci_repair_uses_same_session_not_create_session(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-005",
            github_repository="owner/superset",
            github_issue_number=605,
            github_issue_url="https://github.com/owner/superset/issues/605",
            issue_title="CI repair path",
        )
    )
    await orchestrator.process_task(task.id)
    assert fake_client.calls == 1


def test_tags_use_trigger_source_not_hardcoded_github(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="api:owner/superset:606",
            github_repository="owner/superset",
            github_issue_number=606,
            github_issue_url="https://github.com/owner/superset/issues/606",
            issue_title="Tag source",
            trigger_source="manual_api",
        )
    )
    tags = build_session_tags(task)
    assert "source=api" in tags
    assert "source=github" not in tags


def test_task_response_includes_playbook_id(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="playbook-006",
            github_repository="owner/superset",
            github_issue_number=607,
            github_issue_url="https://github.com/owner/superset/issues/607",
            issue_title="Response playbook",
        )
    )
    task = TaskRepository(db_session).update_task(task, playbook_id="playbook-xyz")
    response = TaskResponse.from_orm_task(task)
    assert response.playbook_id == "playbook-xyz"
