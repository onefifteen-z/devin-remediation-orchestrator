from datetime import UTC, datetime

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.ci import CiCheckRunEvent, FailureType, normalize_check_run_event
from app.schemas.task import TaskCreate
from app.services.ci_handler import CiFailureHandler, build_ci_repair_message
from app.services.failure_classifier import classify
from tests.conftest import load_fixture


def _create_task(db_session, pr_url: str, devin_session_id: str | None = "devin-123"):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="ci-handler-task-001",
            github_repository="owner/superset",
            github_issue_number=44176,
            github_issue_url="https://github.com/owner/superset/issues/44176",
            issue_title="Test issue",
        )
    )
    return repo.update_task(
        task,
        pr_url=pr_url,
        status=TaskStatus.PR_OPENED,
        devin_session_id=devin_session_id,
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_normalize_check_run_event_reads_real_fields():
    payload = load_fixture("check_run_failure.json")
    event = normalize_check_run_event("delivery-1", payload)

    assert event.repository == "owner/superset"
    assert event.check_run_id == 987654321
    assert event.check_name == "Python Unit Tests"
    assert event.status == "completed"
    assert event.conclusion == "failure"
    assert event.pr_numbers == [123]
    assert event.output_summary is not None


def test_build_ci_repair_message_contains_required_sections():
    event = CiCheckRunEvent(
        delivery_id="d1",
        repository="owner/repo",
        action="completed",
        check_run_id=1,
        check_name="Python Unit Tests",
        status="completed",
        conclusion="failure",
        output_summary="pytest failed",
    )
    message = build_ci_repair_message(event)
    assert "Python Unit Tests" in message
    assert "failure" in message
    assert "Do not disable, weaken, or bypass valid tests" in message


def test_handler_returns_no_matching_task(db_session):
    settings = Settings()
    payload = load_fixture("check_run_failure.json")
    event = normalize_check_run_event("d1", payload)
    handler = CiFailureHandler(db_session, settings)

    result = handler.handle(event)
    assert result.outcome == "no_matching_task"


def test_handler_code_failure_with_live_disabled_skips_repair(db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task(db_session, pr_url=pr_url)
    settings = Settings(devin_live_enabled=False)
    event = normalize_check_run_event("d1", load_fixture("check_run_failure.json"))
    handler = CiFailureHandler(db_session, settings)

    result = handler.handle(event)
    assert result.outcome == "processed"
    assert result.repair_message is None


def test_handler_without_devin_session_skips_repair(db_session):
    pr_url = "https://github.com/owner/superset/pull/123"
    _create_task(db_session, pr_url=pr_url, devin_session_id=None)
    settings = Settings(devin_live_enabled=True)
    event = normalize_check_run_event("d1", load_fixture("check_run_failure.json"))
    handler = CiFailureHandler(db_session, settings)

    result = handler.handle(event)
    assert result.outcome == "processed"
    assert result.repair_message is None


def test_cancelled_classifies_transient_not_code():
    event = normalize_check_run_event("d1", load_fixture("check_run_cancelled.json"))
    result = classify(event)
    assert result.failure_type == FailureType.TRANSIENT_FAILURE
