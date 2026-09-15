import pytest

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinSessionResponse
from app.schemas.remediation_result import (
    REMEDIATION_OUTPUT_JSON_SCHEMA,
    parse_remediation_result,
    remediation_result_to_db_fields,
)
from app.schemas.task import TaskCreate
from app.services.orchestration import RemediationOrchestrator
from app.services.session_lifecycle import (
    extract_structured_result_fields,
    map_devin_session_to_task_status,
)
from tests.test_orchestration import FakeDevinClient, _live_settings


def test_remediation_output_schema_has_required_outcome():
    assert REMEDIATION_OUTPUT_JSON_SCHEMA["required"] == ["outcome"]
    assert "success" in REMEDIATION_OUTPUT_JSON_SCHEMA["properties"]["outcome"]["enum"]


def test_parse_valid_structured_output():
    result = parse_remediation_result(
        {
            "outcome": "success",
            "root_cause": "Null pointer",
            "implementation_summary": "Added guard",
            "tests_performed": [{"command": "pytest tests/", "result": "passed"}],
            "residual_risks": ["Edge case untested"],
            "blocker": None,
        }
    )
    assert result is not None
    assert result.outcome == "success"
    assert result.root_cause == "Null pointer"


def test_parse_null_structured_output():
    assert parse_remediation_result(None) is None


def test_parse_malformed_structured_output():
    assert parse_remediation_result({"outcome": "not-valid"}) is None


def test_parse_legacy_status_field():
    result = parse_remediation_result({"status": "failed", "root_cause": "Could not reproduce"})
    assert result is not None
    assert result.outcome == "failed"


def test_parse_structured_output_with_optional_test_category():
    result = parse_remediation_result(
        {
            "outcome": "success",
            "tests_performed": [
                {
                    "command": "pytest -k legacy (with fix stashed)",
                    "result": "failed",
                    "category": "pre_fix_reproduction",
                },
                {
                    "command": "pytest",
                    "result": "passed",
                    "category": "post_fix_validation",
                },
            ],
        }
    )
    assert result is not None
    assert result.tests_performed[0].category == "pre_fix_reproduction"
    assert result.tests_performed[1].category == "post_fix_validation"


def test_remediation_result_persists_fields():
    result = parse_remediation_result(
        {
            "outcome": "blocked",
            "root_cause": "Needs credentials",
            "implementation_summary": "Stopped early",
            "tests_performed": [],
            "residual_risks": ["Manual setup required"],
            "blocker": "Missing API key",
        }
    )
    fields = remediation_result_to_db_fields(result, {"outcome": "blocked"})
    assert fields["remediation_outcome"] == "blocked"
    assert fields["root_cause"] == "Needs credentials"
    assert fields["implementation_summary"] == "Stopped early"
    assert fields["blocker"] == "Missing API key"
    assert "residual_risks" in fields["structured_result_json"]


@pytest.mark.asyncio
async def test_create_session_includes_structured_output_schema(db_session):
    fake_client = FakeDevinClient()
    orchestrator = RemediationOrchestrator(db_session, _live_settings(), devin_client=fake_client)
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="structured-create-001",
            github_repository="owner/superset",
            github_issue_number=501,
            github_issue_url="https://github.com/owner/superset/issues/501",
            issue_title="Structured output test",
        )
    )
    await orchestrator.process_task(task.id)
    assert fake_client.last_structured_output_schema == REMEDIATION_OUTPUT_JSON_SCHEMA
    assert fake_client.last_structured_output_required is True


@pytest.mark.asyncio
async def test_structured_output_persists_on_session_sync(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="structured-persist-001",
            github_repository="owner/superset",
            github_issue_number=502,
            github_issue_url="https://github.com/owner/superset/issues/502",
            issue_title="Persist structured",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.RUNNING,
        devin_session_id="devin-structured",
        devin_session_url="https://app.devin.ai/sessions/devin-structured",
    )
    orchestrator = RemediationOrchestrator(db_session, Settings(), devin_client=FakeDevinClient())
    session = DevinSessionResponse(
        session_id="devin-structured",
        url="https://app.devin.ai/sessions/devin-structured",
        status="exit",
        structured_output={
            "outcome": "success",
            "root_cause": "Race condition",
            "implementation_summary": "Added lock",
            "tests_performed": [{"command": "pytest", "result": "passed"}],
            "residual_risks": ["Load test pending"],
            "blocker": None,
        },
    )
    updated = await orchestrator.apply_session_update(task, session)
    assert updated.root_cause == "Race condition"
    assert updated.implementation_summary == "Added lock"
    assert updated.remediation_outcome == "success"
    assert "Load test pending" in updated.structured_result_json


def test_structured_success_does_not_mark_task_merged(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="structured-success-001",
            github_repository="owner/superset",
            github_issue_number=503,
            github_issue_url="https://github.com/owner/superset/issues/503",
            issue_title="Success not merged",
        )
    )
    task = TaskRepository(db_session).update_status(task, TaskStatus.RUNNING)
    session = DevinSessionResponse(
        session_id="devin-success",
        url="https://app.devin.ai/sessions/devin-success",
        status="exit",
        structured_output={"outcome": "success", "root_cause": "Fixed"},
    )
    target = map_devin_session_to_task_status(task, session)
    assert target == TaskStatus.COMPLETED


def test_blocked_structured_output_escalates(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="structured-blocked-001",
            github_repository="owner/superset",
            github_issue_number=504,
            github_issue_url="https://github.com/owner/superset/issues/504",
            issue_title="Blocked",
        )
    )
    task = TaskRepository(db_session).update_status(task, TaskStatus.RUNNING)
    session = DevinSessionResponse(
        session_id="devin-blocked",
        url="https://app.devin.ai/sessions/devin-blocked",
        status="exit",
        structured_output={"outcome": "blocked", "blocker": "Needs human input"},
    )
    assert map_devin_session_to_task_status(task, session) == TaskStatus.ESCALATED


@pytest.mark.asyncio
async def test_apply_session_update_running_finished_success_completes_without_pr(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="structured-running-finished-001",
            github_repository="owner/superset",
            github_issue_number=512,
            github_issue_url="https://github.com/owner/superset/issues/512",
            issue_title="Already fixed",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.RUNNING,
        devin_session_id="devin-running-finished",
        devin_session_url="https://app.devin.ai/sessions/devin-running-finished",
    )
    orchestrator = RemediationOrchestrator(db_session, Settings(), devin_client=FakeDevinClient())
    session = DevinSessionResponse(
        session_id="devin-running-finished",
        url="https://app.devin.ai/sessions/devin-running-finished",
        status="running",
        status_detail="finished",
        structured_output={
            "outcome": "success",
            "implementation_summary": "Issue already fixed upstream",
        },
    )
    updated = await orchestrator.apply_session_update(task, session)
    assert updated.status == TaskStatus.COMPLETED
    assert updated.completion_reason == "Issue already fixed upstream"


def test_extract_structured_result_fields_empty_when_missing():
    session = DevinSessionResponse(
        session_id="devin-empty",
        url="https://app.devin.ai/sessions/devin-empty",
        status="running",
    )
    assert extract_structured_result_fields(session) == {}
