import enum

from pydantic import BaseModel, Field


class FailureType(str, enum.Enum):
    CODE_FAILURE = "CODE_FAILURE"
    INFRA_FAILURE = "INFRA_FAILURE"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"
    UNKNOWN = "UNKNOWN"


FAILURE_LIKE_CONCLUSIONS = frozenset(
    {
        "failure",
        "cancelled",
        "timed_out",
        "startup_failure",
        "action_required",
        "stale",
    }
)

IGNORED_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})


class CiCheckRunEvent(BaseModel):
    delivery_id: str
    repository: str
    action: str
    check_run_id: int
    check_name: str | None = None
    check_url: str | None = None
    status: str
    conclusion: str | None = None
    head_sha: str | None = None
    pr_numbers: list[int] = Field(default_factory=list)
    output_title: str | None = None
    output_summary: str | None = None


def normalize_check_run_event(delivery_id: str, payload: dict) -> CiCheckRunEvent:
    """Normalize a GitHub check_run webhook payload into CiCheckRunEvent."""
    check_run = payload["check_run"]
    repository = payload["repository"]["full_name"]
    output = check_run.get("output") or {}
    pull_requests = check_run.get("pull_requests") or []
    pr_numbers = [pr["number"] for pr in pull_requests if "number" in pr]

    return CiCheckRunEvent(
        delivery_id=delivery_id,
        repository=repository,
        action=payload.get("action", ""),
        check_run_id=check_run["id"],
        check_name=check_run.get("name"),
        check_url=check_run.get("html_url"),
        status=check_run.get("status", ""),
        conclusion=check_run.get("conclusion"),
        head_sha=check_run.get("head_sha"),
        pr_numbers=pr_numbers,
        output_title=output.get("title"),
        output_summary=output.get("summary"),
    )
