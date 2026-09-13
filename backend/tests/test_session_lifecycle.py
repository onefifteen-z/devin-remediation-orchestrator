import pytest

from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinPullRequest, DevinSessionResponse
from app.schemas.task import TaskCreate
from app.services.session_lifecycle import (
    extract_devin_audit_fields,
    extract_primary_pull_request,
    map_devin_session_to_task_status,
)


def _task(db_session, status: TaskStatus = TaskStatus.RUNNING):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=f"lifecycle-{status.value}",
            github_repository="owner/superset",
            github_issue_number=100,
            github_issue_url="https://github.com/owner/superset/issues/100",
            issue_title="Lifecycle test",
        )
    )
    return repo.update_status(
        task,
        status,
        devin_session_id="devin-test-001",
        devin_session_url="https://app.devin.ai/sessions/devin-test-001",
    )


def _session(status: str, **kwargs) -> DevinSessionResponse:
    return DevinSessionResponse(
        session_id="devin-test-001",
        url="https://app.devin.ai/sessions/devin-test-001",
        status=status,
        **kwargs,
    )


@pytest.mark.parametrize(
    ("devin_status", "task_status", "expected"),
    [
        ("new", TaskStatus.RECEIVED, TaskStatus.SESSION_CREATED),
        ("claimed", TaskStatus.SESSION_CREATED, TaskStatus.SESSION_CREATED),
        ("running", TaskStatus.SESSION_CREATED, TaskStatus.RUNNING),
        ("resuming", TaskStatus.RUNNING, TaskStatus.RUNNING),
        ("suspended", TaskStatus.RUNNING, None),
        ("error", TaskStatus.RUNNING, TaskStatus.FAILED),
    ],
)
def test_status_mapping_documented_values(db_session, devin_status, task_status, expected):
    task = _task(db_session, task_status)
    result = map_devin_session_to_task_status(task, _session(devin_status))
    assert result == expected


def test_status_mapping_running_with_pr(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session(
        "running",
        pull_requests=[DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open")],
    )
    assert map_devin_session_to_task_status(task, session) == TaskStatus.PR_OPENED


def test_status_mapping_exit_with_pr(db_session):
    task = _task(db_session, TaskStatus.PR_OPENED)
    session = _session(
        "exit",
        pull_requests=[DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open")],
    )
    assert map_devin_session_to_task_status(task, session) == TaskStatus.READY_FOR_REVIEW


def test_status_mapping_exit_without_pr(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session("exit")
    assert map_devin_session_to_task_status(task, session) == TaskStatus.FAILED


def test_status_mapping_exit_with_failed_structured_output(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session("exit", structured_output={"status": "failed", "root_cause": "Could not reproduce"})
    assert map_devin_session_to_task_status(task, session) == TaskStatus.FAILED


def test_status_mapping_exit_with_blocked_structured_output(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session(
        "exit",
        structured_output={"status": "blocked", "blocked_reason": "Needs human input"},
    )
    assert map_devin_session_to_task_status(task, session) == TaskStatus.ESCALATED


def test_status_mapping_unknown_status(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    assert map_devin_session_to_task_status(task, _session("completed")) is None


def test_status_mapping_suspended_usage_limit_escalates(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session("suspended", status_detail="usage_limit_exceeded")
    assert map_devin_session_to_task_status(task, session) == TaskStatus.ESCALATED


def test_status_mapping_suspended_usage_limit_with_pr_stays_pr_opened(db_session):
    task = _task(db_session, TaskStatus.PR_OPENED)
    session = _session(
        "suspended",
        status_detail="usage_limit_exceeded",
        pull_requests=[DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open")],
    )
    assert map_devin_session_to_task_status(task, session) is None


def test_status_mapping_suspended_inactivity_no_change(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session("suspended", status_detail="inactivity")
    assert map_devin_session_to_task_status(task, session) is None


def test_status_mapping_suspended_from_session_created_no_change(db_session):
    task = _task(db_session, TaskStatus.SESSION_CREATED)
    session = _session("suspended", status_detail="inactivity")
    assert map_devin_session_to_task_status(task, session) is None


def test_status_mapping_error_with_pr_stays_pr_opened(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session(
        "error",
        pull_requests=[DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open")],
    )
    assert map_devin_session_to_task_status(task, session) == TaskStatus.PR_OPENED


def test_status_mapping_running_waiting_for_user_stays_running(db_session):
    task = _task(db_session, TaskStatus.RUNNING)
    session = _session("running", status_detail="waiting_for_user")
    assert map_devin_session_to_task_status(task, session) is None


def test_extract_devin_audit_fields():
    session = _session(
        "running",
        status_detail="working",
        origin="api",
        service_user_id="svc-123",
        tags=["source=github"],
    )
    fields = extract_devin_audit_fields(session)
    assert fields["devin_status"] == "running"
    assert fields["devin_status_detail"] == "working"
    assert fields["devin_origin"] == "api"
    assert fields["devin_service_user_id"] == "svc-123"
    assert '"source=github"' in fields["devin_tags"]


def test_extract_primary_pull_request_none():
    assert extract_primary_pull_request([]) is None


def test_extract_primary_pull_request_one():
    prs = [DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open")]
    assert extract_primary_pull_request(prs) == ("https://github.com/org/repo/pull/1", "open")


def test_extract_primary_pull_request_multiple():
    prs = [
        DevinPullRequest(pr_url="https://github.com/org/repo/pull/1", pr_state="open"),
        DevinPullRequest(pr_url="https://github.com/org/repo/pull/2", pr_state="draft"),
    ]
    assert extract_primary_pull_request(prs) == ("https://github.com/org/repo/pull/1", "open")
