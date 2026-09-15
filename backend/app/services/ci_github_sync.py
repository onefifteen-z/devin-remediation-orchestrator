import logging
import re
from datetime import UTC, datetime

from app.models.task import RemediationTask
from app.repositories.tasks import TaskRepository
from app.services.github import GitHubAPIError, GitHubClient

logger = logging.getLogger(__name__)

_PR_NUMBER_RE = re.compile(r"/pull/(\d+)(?:/|$)")
_SUCCESS_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})
_IN_PROGRESS_STATUSES = frozenset({"queued", "in_progress", "pending", "waiting"})


def pr_number_from_url(pr_url: str) -> int | None:
    match = _PR_NUMBER_RE.search(pr_url)
    return int(match.group(1)) if match else None


def _commit_statuses_pass(statuses: list[dict]) -> bool:
    if not statuses:
        return False
    for status in statuses:
        state = (status.get("state") or "").lower()
        if state in {"failure", "error", "pending"}:
            return False
    return all((status.get("state") or "").lower() == "success" for status in statuses)


def github_ci_passes(combined_status: dict, check_runs: list[dict]) -> bool:
    state = (combined_status.get("state") or "").lower()
    if state == "success":
        return True
    if state in {"failure", "error"}:
        return False

    statuses = combined_status.get("statuses") or []
    if _commit_statuses_pass(statuses):
        return True

    if not check_runs:
        return False

    completed = [run for run in check_runs if run.get("status") == "completed"]
    in_progress = [
        run for run in check_runs if run.get("status") in _IN_PROGRESS_STATUSES
    ]
    if in_progress:
        return False
    if not completed:
        return False

    return all((run.get("conclusion") or "").lower() in _SUCCESS_CONCLUSIONS for run in completed)


async def sync_ci_pass_from_github(
    task: RemediationTask,
    github_client: GitHubClient,
    repo: TaskRepository,
) -> RemediationTask:
    """Backfill ci_passed_at from GitHub when check_run webhooks were missed."""
    if not task.pr_url:
        return task
    if task.ci_passed_at or task.ci_repair_verified_at:
        return task
    if task.ci_failure_at and task.ci_repair_verified_at is None:
        return task
    if task.pr_state and task.pr_state.lower() == "closed":
        return task

    pr_number = pr_number_from_url(task.pr_url)
    if pr_number is None:
        return task

    try:
        pr_data = await github_client.get_pull_request(task.github_repository, pr_number)
        head_sha = pr_data.get("head", {}).get("sha")
        if not head_sha:
            return task

        combined_status = await github_client.get_commit_combined_status(
            task.github_repository,
            head_sha,
        )
        check_runs = await github_client.list_check_runs_for_ref(
            task.github_repository,
            head_sha,
        )
    except GitHubAPIError as exc:
        logger.warning(
            "ci_github_sync_failed",
            extra={
                "task_id": task.id,
                "repository": task.github_repository,
                "pr_number": pr_number,
                "status_code": exc.status_code,
            },
        )
        return task

    if not github_ci_passes(combined_status, check_runs):
        return task

    updated = repo.update_task(task, ci_passed_at=datetime.now(UTC))
    logger.info(
        "ci_passed_backfilled_from_github",
        extra={
            "task_id": task.id,
            "repository": task.github_repository,
            "pr_number": pr_number,
            "combined_state": combined_status.get("state"),
            "check_run_count": len(check_runs),
        },
    )
    return updated
