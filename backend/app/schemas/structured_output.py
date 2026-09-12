from typing import Literal

from pydantic import BaseModel, Field


class RemediationResult(BaseModel):
    """Internal schema for future Devin structured_output_schema consumption."""

    status: Literal["success", "blocked", "failed"]
    root_cause: str | None = None
    summary: str | None = None
    tests_run: list[str] = Field(default_factory=list)
    pr_url: str | None = None
    risk: Literal["low", "medium", "high"] | None = None
    blocked_reason: str | None = None
