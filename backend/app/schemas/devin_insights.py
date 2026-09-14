from typing import Any

from pydantic import BaseModel, Field


class InsightsClassification(BaseModel):
    category: str | None = None
    confidence: float | None = None
    programming_languages: list[str] = Field(default_factory=list)
    tools_and_frameworks: list[str] = Field(default_factory=list)


class InsightsIssue(BaseModel):
    id: str = ""
    title: str = ""
    issue: str
    impact: str
    label: str


class InsightsTimelineEvent(BaseModel):
    title: str
    description: str
    color: str = ""
    issue_id: str | None = None


class InsightsActionItem(BaseModel):
    action_item: str
    type: str = "other"
    issue_id: str | None = None


class InsightsAnalysis(BaseModel):
    """Subset of Devin's AI-generated session analysis surfaced on the dashboard."""

    classification: InsightsClassification | None = None
    issues: list[InsightsIssue] = Field(default_factory=list)
    timeline: list[InsightsTimelineEvent] = Field(default_factory=list)
    action_items: list[InsightsActionItem] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.classification or self.issues or self.timeline or self.action_items)


class SessionInsights(BaseModel):
    session_id: str
    session_size: str | None = None
    num_user_messages: int | None = None
    num_devin_messages: int | None = None
    analysis_status: str | None = None
    analysis: InsightsAnalysis | None = None


def parse_session_insights(data: dict[str, Any]) -> SessionInsights:
    if "session_id" not in data:
        raise ValueError("Missing required session_id field")
    return SessionInsights.model_validate(data)


def parse_session_insights_list(data: dict[str, Any]) -> list[SessionInsights]:
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("Missing items in session insights response")
    return [parse_session_insights(item) for item in items if isinstance(item, dict)]
