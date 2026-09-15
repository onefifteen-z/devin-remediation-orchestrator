from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.ci_github_sync import (
    github_ci_passes,
    pr_number_from_url,
    sync_ci_pass_from_github,
)


def test_pr_number_from_url():
    assert pr_number_from_url("https://github.com/onefifteen-z/superset/pull/10") == 10
    assert pr_number_from_url("https://github.com/owner/repo/pull/99/files") == 99
    assert pr_number_from_url("https://github.com/owner/repo/issues/1") is None


def test_github_ci_passes_combined_success():
    assert github_ci_passes({"state": "success"}, []) is True


def test_github_ci_passes_failed_combined_status():
    assert github_ci_passes({"state": "failure"}, [{"status": "completed", "conclusion": "success"}]) is False


def test_github_ci_passes_commit_statuses_only():
    statuses = [{"state": "success"}, {"state": "success"}]
    assert github_ci_passes({"state": "pending", "statuses": statuses}, []) is True


def test_github_ci_passes_all_check_runs_green():
    check_runs = [
        {"status": "completed", "conclusion": "success"},
        {"status": "completed", "conclusion": "skipped"},
    ]
    assert github_ci_passes({"state": "pending"}, check_runs) is True


def test_github_ci_passes_in_progress_check_runs():
    check_runs = [
        {"status": "in_progress", "conclusion": None},
        {"status": "completed", "conclusion": "success"},
    ]
    assert github_ci_passes({"state": "pending"}, check_runs) is False


def _create_task_with_pr(db_session, pr_url: str):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="ci-sync-001",
            github_repository="onefifteen-z/superset",
            github_issue_number=10,
            github_issue_url="https://github.com/onefifteen-z/superset/issues/10",
            issue_title="CI stuck",
        )
    )
    return repo.update_task(
        task,
        pr_url=pr_url,
        status=TaskStatus.READY_FOR_REVIEW,
        devin_session_id="devin-session-10",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_sync_ci_pass_from_github_backfills_ci_passed_at(db_session):
    pr_url = "https://github.com/onefifteen-z/superset/pull/10"
    task = _create_task_with_pr(db_session, pr_url)
    repo = TaskRepository(db_session)

    github_client = AsyncMock()
    github_client.get_pull_request.return_value = {"head": {"sha": "abc123"}}
    github_client.get_commit_combined_status.return_value = {"state": "success"}
    github_client.list_check_runs_for_ref.return_value = [
        {"status": "completed", "conclusion": "success"},
    ]

    updated = await sync_ci_pass_from_github(task, github_client, repo)

    assert updated.ci_passed_at is not None
    refreshed = repo.get_by_id(task.id)
    assert refreshed.ci_passed_at is not None


@pytest.mark.asyncio
async def test_sync_ci_pass_skips_when_already_set(db_session):
    pr_url = "https://github.com/onefifteen-z/superset/pull/10"
    task = _create_task_with_pr(db_session, pr_url)
    repo = TaskRepository(db_session)
    passed_at = datetime(2026, 2, 1, tzinfo=UTC)
    task = repo.update_task(task, ci_passed_at=passed_at)

    github_client = AsyncMock()

    updated = await sync_ci_pass_from_github(task, github_client, repo)

    assert updated.ci_passed_at is not None
    github_client.get_pull_request.assert_not_called()


@pytest.mark.asyncio
async def test_sync_ci_pass_skips_when_ci_failed(db_session):
    pr_url = "https://github.com/onefifteen-z/superset/pull/10"
    task = _create_task_with_pr(db_session, pr_url)
    repo = TaskRepository(db_session)
    task = repo.update_task(task, ci_failure_at=datetime(2026, 2, 1, tzinfo=UTC))

    github_client = AsyncMock()
    github_client.get_pull_request.return_value = {"head": {"sha": "abc123"}}
    github_client.get_commit_combined_status.return_value = {"state": "success"}
    github_client.list_check_runs_for_ref.return_value = []

    updated = await sync_ci_pass_from_github(task, github_client, repo)

    assert updated.ci_passed_at is None
