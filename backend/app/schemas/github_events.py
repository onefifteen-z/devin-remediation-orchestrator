from datetime import UTC, datetime

from pydantic import BaseModel

REMEDIATE_LABEL = "devin-remediate"


class PullRequestEvent(BaseModel):
    delivery_id: str
    event_type: str = "pull_request"
    action: str
    repository: str
    pr_number: int
    pr_url: str
    pr_state: str
    merged: bool
    merged_at: datetime | None
    head_sha: str | None = None


def extract_issue_type(labels: list[dict], remediate_label: str = REMEDIATE_LABEL) -> str:
    for label in labels:
        name = label.get("name", "")
        if name != remediate_label:
            return name
    return "unknown"


def extract_issue_labels(
    labels: list[dict], remediate_label: str = REMEDIATE_LABEL
) -> list[str]:
    """All domain labels, excluding the trigger label the Source column covers."""
    return [
        name
        for label in labels
        if (name := label.get("name", "")) and name != remediate_label
    ]


def normalize_issue_event(delivery_id: str, payload: dict) -> dict:
    """Normalize a GitHub issues webhook payload into RemediationEvent fields."""
    issue = payload["issue"]
    repository = payload["repository"]["full_name"]
    labels = issue.get("labels", [])
    return {
        "github_delivery_id": delivery_id,
        "source": "github",
        "github_repository": repository,
        "github_issue_number": issue["number"],
        "github_issue_url": issue["html_url"],
        "issue_title": issue.get("title", ""),
        "issue_body": issue.get("body"),
        "issue_type": extract_issue_type(labels),
        "issue_labels": extract_issue_labels(labels),
        "action": payload.get("action"),
    }


def _parse_github_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


def normalize_pull_request_event(delivery_id: str, payload: dict) -> PullRequestEvent:
    pull_request = payload["pull_request"]
    repository = payload["repository"]["full_name"]
    return PullRequestEvent(
        delivery_id=delivery_id,
        action=payload["action"],
        repository=repository,
        pr_number=pull_request["number"],
        pr_url=pull_request["html_url"],
        pr_state=pull_request["state"],
        merged=bool(pull_request.get("merged", False)),
        merged_at=_parse_github_timestamp(pull_request.get("merged_at")),
        head_sha=pull_request.get("head", {}).get("sha"),
    )
