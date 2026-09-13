from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlaybookInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")

    playbook_id: str
    title: str | None = None


class ScheduleCreateRequest(BaseModel):
    name: str
    prompt: str
    schedule_type: str = "recurring"
    frequency: str | None = None
    playbook_id: str | None = None
    tags: list[str] | None = None


class ScheduleUpdateRequest(BaseModel):
    name: str | None = None
    prompt: str | None = None
    schedule_type: str | None = None
    frequency: str | None = None
    playbook_id: str | None = None
    tags: list[str] | None = None
    enabled: bool | None = None


class ScheduleResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schedule_id: str
    scheduled_session_id: str | None = None
    name: str | None = None
    prompt: str | None = None
    schedule_type: str | None = None
    frequency: str | None = None
    enabled: bool | None = None
    tags: list[str] = Field(default_factory=list)
    playbook: PlaybookInfo | None = None


def build_schedule_create_body(
    *,
    name: str,
    prompt: str,
    frequency: str,
    tags: list[str] | None = None,
    playbook_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": name,
        "prompt": prompt,
        "schedule_type": "recurring",
        "frequency": frequency,
    }
    if tags:
        body["tags"] = tags
    if playbook_id:
        body["playbook_id"] = playbook_id
    return body


def build_schedule_update_body(
    *,
    name: str,
    prompt: str,
    frequency: str,
    tags: list[str] | None = None,
    playbook_id: str | None = None,
    enabled: bool = True,
) -> dict[str, Any]:
    body = build_schedule_create_body(
        name=name,
        prompt=prompt,
        frequency=frequency,
        tags=tags,
        playbook_id=playbook_id,
    )
    body["enabled"] = enabled
    return body


def parse_schedule_response(data: dict[str, Any]) -> ScheduleResponse:
    schedule_id = data.get("scheduled_session_id") or data.get("schedule_id")
    if not schedule_id:
        raise ValueError("Missing schedule identifier")

    playbook_raw = data.get("playbook")
    playbook = None
    if isinstance(playbook_raw, dict):
        playbook = PlaybookInfo.model_validate(playbook_raw)

    tags_raw = data.get("tags") or []
    tags = [str(tag) for tag in tags_raw] if isinstance(tags_raw, list) else []

    return ScheduleResponse(
        schedule_id=str(schedule_id),
        scheduled_session_id=data.get("scheduled_session_id"),
        name=data.get("name"),
        prompt=data.get("prompt"),
        schedule_type=data.get("schedule_type"),
        frequency=data.get("frequency"),
        enabled=data.get("enabled"),
        tags=tags,
        playbook=playbook,
    )
