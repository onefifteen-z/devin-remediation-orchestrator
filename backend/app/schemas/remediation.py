from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.task import TaskResponse


class RemediationCreateRequest(BaseModel):
    repository: str = Field(description="GitHub repository in owner/repo format")
    issue_number: int
    issue_url: str
    issue_type: str = "unknown"


RemediationOutcome = Literal[
    "created",
    "skipped",
    "duplicate_issue_trigger",
    "duplicate_webhook_delivery",
    "existing_active",
    "existing_devin_session",
    "already_remediated",
    "existing_terminal",
]


class RemediationResponse(BaseModel):
    outcome: RemediationOutcome
    devin_live_enabled: bool
    message: str
    task: TaskResponse
