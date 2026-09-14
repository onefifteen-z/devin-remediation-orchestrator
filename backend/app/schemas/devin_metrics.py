from typing import Any

from pydantic import BaseModel, Field


class OrgUsageMetrics(BaseModel):
    sessions_count: int = 0
    searches_count: int = 0
    prs_created_count: int = 0
    prs_merged_count: int = 0


class OrgPrMetrics(BaseModel):
    prs_created_count: int = 0
    prs_opened_count: int = 0
    prs_merged_count: int = 0
    prs_closed_count: int = 0
    prs_taken_over_count: int = 0
    prs_taken_over_opened_count: int = 0
    prs_taken_over_merged_count: int = 0
    prs_taken_over_closed_count: int = 0


class OrgSessionMetrics(BaseModel):
    sessions_created_count: int = 0
    sessions_created_by_size: dict[str, int] = Field(default_factory=dict)
    sessions_created_by_origin: dict[str, int] = Field(default_factory=dict)
    sessions_created_with_playbook_count: int = 0
    sessions_created_with_search_count: int = 0
    sessions_with_merged_prs_count: int = 0
    sessions_with_merged_prs_by_size: dict[str, int] = Field(default_factory=dict)
    avg_acus_per_session: float = 0.0


class OrgActiveUsersPoint(BaseModel):
    start_time: int
    end_time: int
    active_users: int = 0


class OrgMetricsSnapshot(BaseModel):
    """Devin org-wide metrics for a single time window.

    Counts cover every session in the Devin organization, not just orchestrator
    remediation tasks, so these must not be mixed with task-derived metrics.
    """

    window_start: int
    window_end: int
    usage: OrgUsageMetrics
    pull_requests: OrgPrMetrics
    sessions: OrgSessionMetrics
    active_users: int = 0
    peak_dau: int = 0
    peak_wau: int = 0
    peak_mau: int = 0


def parse_org_usage_metrics(data: dict[str, Any]) -> OrgUsageMetrics:
    return OrgUsageMetrics.model_validate(data)


def parse_org_pr_metrics(data: dict[str, Any]) -> OrgPrMetrics:
    return OrgPrMetrics.model_validate(data)


def parse_org_session_metrics(data: dict[str, Any]) -> OrgSessionMetrics:
    return OrgSessionMetrics.model_validate(data)


def parse_org_active_users(data: dict[str, Any]) -> OrgActiveUsersPoint:
    return OrgActiveUsersPoint.model_validate(data)


def parse_org_active_users_series(data: Any) -> list[OrgActiveUsersPoint]:
    if not isinstance(data, list):
        raise ValueError("Expected a list of active user buckets")
    return [OrgActiveUsersPoint.model_validate(point) for point in data]


def peak_active_users(series: list[OrgActiveUsersPoint]) -> int:
    """Peak rather than latest: the final bucket is the in-progress period.

    Devin returns a trailing bucket for the current day/week/month, which reads
    as 0 until activity lands in it.
    """
    return max((point.active_users for point in series), default=0)
