import json
import logging

from app.models.task import RemediationTask, TaskStatus
from app.schemas.devin_insights import SessionInsights
from app.schemas.devin_session import DevinPullRequest, DevinSessionResponse
from app.schemas.remediation_result import (
    parse_remediation_result,
    remediation_result_to_db_fields,
)

logger = logging.getLogger(__name__)

DOCUMENTED_DEVIN_STATUSES = frozenset(
    {"new", "claimed", "running", "exit", "error", "suspended", "resuming"}
)

SUSPENDED_ESCALATION_DETAILS = frozenset({"usage_limit_exceeded", "out_of_credits"})

DOCUMENTED_STATUS_DETAILS = frozenset(
    {
        "usage_limit_exceeded",
        "out_of_credits",
        "user_request",
        "inactivity",
        "working",
        "waiting_for_user",
        "waiting_for_approval",
        "finished",
    }
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

TERMINAL_DEVIN_STATUSES = frozenset({"exit", "error"})


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


def extract_devin_audit_fields(session: DevinSessionResponse) -> dict:
    """Build DB field updates from raw Devin session state."""
    if session.status_detail and session.status_detail not in DOCUMENTED_STATUS_DETAILS:
        logger.warning(
            "Unknown Devin status_detail",
            extra={
                "devin_session_id": session.session_id,
                "status_detail": session.status_detail,
            },
        )

    fields: dict = {
        "devin_status": session.status,
        "devin_status_detail": session.status_detail,
        "devin_origin": session.origin,
        "devin_service_user_id": session.service_user_id,
    }
    if session.tags:
        fields["devin_tags"] = json.dumps(session.tags)
    if session.playbook_id:
        fields["playbook_id"] = session.playbook_id
    return fields


def extract_session_insights_fields(insights: SessionInsights) -> dict:
    """Build DB field updates from Devin session insights."""
    analysis = insights.analysis
    return {
        "session_size": insights.session_size,
        "num_user_messages": insights.num_user_messages,
        "num_devin_messages": insights.num_devin_messages,
        "insights_status": insights.analysis_status,
        "insights_json": (
            analysis.model_dump_json() if analysis is not None and not analysis.is_empty() else None
        ),
    }


def _parse_structured_output(session: DevinSessionResponse):
    return parse_remediation_result(
        session.structured_output,
        devin_session_id=session.session_id,
    )


def extract_structured_result_fields(session: DevinSessionResponse) -> dict:
    structured = _parse_structured_output(session)
    if structured is None or session.structured_output is None:
        return {}
    return remediation_result_to_db_fields(structured, session.structured_output)


def _resolve_exit_status(
    session: DevinSessionResponse,
    pr: tuple[str, str | None] | None,
) -> TaskStatus:
    if pr is not None:
        return TaskStatus.READY_FOR_REVIEW

    structured = _parse_structured_output(session)
    if structured:
        if structured.outcome == "failed":
            return TaskStatus.FAILED
        if structured.outcome == "blocked":
            return TaskStatus.ESCALATED

    return TaskStatus.FAILED


def _resolve_suspended_status(
    session: DevinSessionResponse,
    pr: tuple[str, str | None] | None,
) -> TaskStatus | None:
    detail = (session.status_detail or "").lower()
    if detail in SUSPENDED_ESCALATION_DETAILS:
        if pr is not None:
            return TaskStatus.PR_OPENED
        return TaskStatus.ESCALATED
    return None


def map_devin_session_to_task_status(
    task: RemediationTask,
    session: DevinSessionResponse,
) -> TaskStatus | None:
    """Map Devin session state to workflow status. Returns None when unchanged."""
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
    elif devin_status in {"running", "resuming"}:
        if pr is not None:
            target = TaskStatus.PR_OPENED
        else:
            target = TaskStatus.RUNNING
    elif devin_status == "suspended":
        target = _resolve_suspended_status(session, pr)
    elif devin_status == "error":
        target = TaskStatus.PR_OPENED if pr is not None else TaskStatus.FAILED
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


def is_terminal_devin_status(status: str) -> bool:
    return status.lower() in TERMINAL_DEVIN_STATUSES


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
    if structured and structured.outcome == "failed":
        return (
            structured.implementation_summary
            or structured.root_cause
            or "Devin reported failure"
        )
    if pr is None and session.status.lower() == "exit":
        return "Session exited without pull request"
    return None


def resolve_exit_escalation_reason(
    session: DevinSessionResponse,
    target: TaskStatus,
) -> str | None:
    if target != TaskStatus.ESCALATED:
        return None
    detail = (session.status_detail or "").lower()
    if session.status.lower() == "suspended" and detail in SUSPENDED_ESCALATION_DETAILS:
        return f"Devin session suspended: {session.status_detail}"
    structured = _parse_structured_output(session)
    if structured and structured.outcome == "blocked":
        return structured.blocker or "Devin session blocked"
    return None
