from typing import Any

from pydantic import BaseModel, Field


class ScheduleCreateRequest(BaseModel):
    title: str
    prompt: str
    schedule_type: str
    frequency: str | None = None
    playbook_id: str | None = None
    tags: list[str] | None = None
    enabled: bool = True


class ScheduleResponse(BaseModel):
    schedule_id: str
    title: str
    prompt: str
    schedule_type: str
    frequency: str | None = None
    playbook_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True


def parse_schedule_response(data: dict[str, Any]) -> ScheduleResponse:
    if "schedule_id" not in data:
        raise ValueError("Missing schedule_id")
    return ScheduleResponse.model_validate(data)
