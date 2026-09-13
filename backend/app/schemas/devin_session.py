from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DevinPullRequest(BaseModel):
    pr_url: str | None = None
    pr_state: str | None = None


class DevinSessionResponse(BaseModel):
    session_id: str
    url: str
    status: str
    status_detail: str | None = None
    origin: str | None = None
    service_user_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    pull_requests: list[DevinPullRequest] = Field(default_factory=list)
    acus_consumed: float | None = None
    structured_output: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def parse_pull_request(raw: dict[str, Any]) -> DevinPullRequest:
    pr_url = raw.get("pr_url") or raw.get("url")
    pr_state = raw.get("pr_state") or raw.get("state")
    return DevinPullRequest(
        pr_url=str(pr_url) if pr_url else None,
        pr_state=str(pr_state) if pr_state else None,
    )


def parse_devin_session_response(data: dict[str, Any]) -> DevinSessionResponse:
    if "session_id" not in data or "url" not in data:
        raise ValueError("Missing required session fields")

    pull_requests_raw = data.get("pull_requests") or []
    pull_requests = [
        parse_pull_request(pr) for pr in pull_requests_raw if isinstance(pr, dict)
    ]

    structured_output = data.get("structured_output")
    if structured_output is not None and not isinstance(structured_output, dict):
        structured_output = None

    acus_consumed = data.get("acus_consumed")
    if acus_consumed is not None:
        acus_consumed = float(acus_consumed)

    status_detail = data.get("status_detail")
    origin = data.get("origin")
    service_user_id = data.get("service_user_id")

    tags_raw = data.get("tags") or []
    tags = [str(tag) for tag in tags_raw if tag is not None] if isinstance(tags_raw, list) else []

    return DevinSessionResponse(
        session_id=data["session_id"],
        url=data["url"],
        status=str(data.get("status", "unknown")),
        status_detail=str(status_detail) if status_detail else None,
        origin=str(origin) if origin else None,
        service_user_id=str(service_user_id) if service_user_id else None,
        tags=tags,
        pull_requests=pull_requests,
        acus_consumed=acus_consumed,
        structured_output=structured_output,
        created_at=data.get("created_at"),
        updated_at=data.get("updated_at"),
    )
