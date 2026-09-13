from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.task import TaskResponse


class RemediationCreateRequest(BaseModel):
    repository: str = Field(description="GitHub repository in owner/repo format")
    issue_number: int
    issue_url: str
    issue_type: str = "unknown"


class RemediationResponse(BaseModel):
    outcome: Literal["created", "skipped"]
    devin_live_enabled: bool
    message: str
    task: TaskResponse
