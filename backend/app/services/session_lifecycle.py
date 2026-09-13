import logging

from app.models.task import RemediationTask, TaskStatus
from app.schemas.devin_session import DevinPullRequest, DevinSessionResponse
from app.schemas.structured_output import RemediationResult

logger = logging.getLogger(__name__)

DOCUMENTED_DEVIN_STATUSES = frozenset(
    {"new", "claimed", "running", "exit", "error", "suspended", "resuming"}
)

STATUS_ORDER = {
    TaskStatus.RECEIVED: 0,
    TaskStatus.SESSION_CREATED: 1,
    TaskStatus.RUNNING: 2,
    TaskStatus.PR_OPENED: 3,
    TaskStatus.CI_FAILED: 4,
    TaskStatus.READY_FOR_REVIEW: 5,
    TaskStatus.MERGED: 6,
    TaskStatus.FAILED: 6,
    TaskStatus.ESCALATED: 6,
}


def extract_primary_pull_request(
    pull_requests: list[DevinPullRequest],
) -> tuple[str, str | None] | None:
    """Return the first PR with a URL. When multiple PRs exist, the first wins."""
    if len(pull_requests) > 1:
        logger.info(
            "Multiple pull requests in Devin session; using first",
            extra={"pull_request_count": len(pull_requests)},
        )
    for pr in pull_requests:
        if pr.pr_url:
            return pr.pr_url, pr.pr_state
    return None


def _parse_structured_output(session: DevinSessionResponse) -> RemediationResult | None:
    if not session.structured_output:
        return None
    try:
        return RemediationResult.model_validate(session.structured_output)
    except Exception:
        logger.warning(
            "Unable to parse Devin structured_output",
            extra={"devin_session_id": session.session_id},
        )
        return None


def _resolve_exit_status(
    session: DevinSessionResponse,
    pr: tuple[str, str | None] | None,
) -> TaskStatus:
    if pr is not None:
        return TaskStatus.READY_FOR_REVIEW

    structured = _parse_structured_output(session)
    if structured:
        if structured.status == "failed":
            return TaskStatus.FAILED
        if structured.status == "blocked":
            return TaskStatus.ESCALATED

    return TaskStatus.FAILED


def map_devin_session_to_task_status(
    task: RemediationTask,
    session: DevinSessionResponse,
) -> TaskStatus | None:
    """Map Devin session state to internal task status. Returns None when unchanged."""
    devin_status = session.status.lower()
    pr = extract_primary_pull_request(session.pull_requests)

    if devin_status not in DOCUMENTED_DEVIN_STATUSES:
        logger.warning(
            "Unknown Devin session status",
            extra={
                "devin_session_id": session.session_id,
                "devin_status": session.status,
                "task_id": task.id,
            },
        )
        return None

    target: TaskStatus | None = None

    if devin_status in {"new", "claimed"}:
        if task.status in {TaskStatus.RECEIVED, TaskStatus.SESSION_CREATED}:
            target = TaskStatus.SESSION_CREATED
        elif pr is not None:
            target = TaskStatus.PR_OPENED
    elif devin_status in {"running", "resuming", "suspended"}:
        if pr is not None:
            target = TaskStatus.PR_OPENED
        else:
            target = TaskStatus.RUNNING
    elif devin_status == "error":
        target = TaskStatus.FAILED
    elif devin_status == "exit":
        target = _resolve_exit_status(session, pr)

    if target is None or target == task.status:
        return None

    if not is_valid_status_transition(task.status, target):
        logger.info(
            "Skipping invalid status regression",
            extra={
                "task_id": task.id,
                "from_status": task.status.value,
                "to_status": target.value,
                "devin_status": session.status,
            },
        )
        return None

    return target


def is_valid_status_transition(current: TaskStatus, target: TaskStatus) -> bool:
    if current in {TaskStatus.MERGED, TaskStatus.FAILED, TaskStatus.ESCALATED}:
        return False
    if target == current:
        return False
    return STATUS_ORDER.get(target, 0) >= STATUS_ORDER.get(current, 0)


def resolve_exit_failure_reason(
    session: DevinSessionResponse,
    pr: tuple[str, str | None] | None,
    target: TaskStatus,
) -> str | None:
    if target != TaskStatus.FAILED:
        return None
    if session.status.lower() == "error":
        return "Devin session reported error status"
    structured = _parse_structured_output(session)
    if structured and structured.status == "failed":
        return structured.summary or structured.root_cause or "Devin reported failure"
    if pr is None and session.status.lower() == "exit":
        return "Session exited without pull request"
    return None


def resolve_exit_escalation_reason(
    session: DevinSessionResponse,
    target: TaskStatus,
) -> str | None:
    if target != TaskStatus.ESCALATED:
        return None
    structured = _parse_structured_output(session)
    if structured and structured.status == "blocked":
        return structured.blocked_reason or "Devin session blocked"
    return None
