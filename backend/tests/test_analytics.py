import httpx
import pytest
import respx

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.devin import DevinClient
from app.services.devin_analytics import DevinAnalyticsService
from app.services.metrics import MetricsService


@pytest.fixture
def devin_settings():
    return Settings(
        devin_api_key="cog_test_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )


ORG_METRICS_BASE = "https://api.devin.ai/v3/organizations/org-test123/metrics"


def mock_org_metrics(*, dau=None, wau=None, mau=None):
    respx.get(f"{ORG_METRICS_BASE}/usage").mock(
        return_value=httpx.Response(
            200,
            json={
                "sessions_count": 8,
                "searches_count": 0,
                "prs_created_count": 3,
                "prs_merged_count": 2,
            },
        )
    )
    respx.get(f"{ORG_METRICS_BASE}/prs").mock(
        return_value=httpx.Response(
            200,
            json={
                "prs_created_count": 3,
                "prs_opened_count": 0,
                "prs_merged_count": 2,
                "prs_closed_count": 1,
                "prs_taken_over_count": 0,
                "prs_taken_over_opened_count": 0,
                "prs_taken_over_merged_count": 0,
                "prs_taken_over_closed_count": 0,
            },
        )
    )
    respx.get(f"{ORG_METRICS_BASE}/sessions").mock(
        return_value=httpx.Response(
            200,
            json={
                "sessions_created_count": 8,
                "sessions_created_by_size": {"xs": 8, "s": 0, "m": 0, "l": 0, "xl": 0},
                "sessions_created_by_origin": {"api": 6, "webapp": 1, "automation": 1, "slack": 0},
                "sessions_created_with_playbook_count": 1,
                "sessions_created_with_search_count": 0,
                "sessions_with_merged_prs_count": 2,
                "sessions_with_merged_prs_by_size": {"xs": 2},
                "avg_acus_per_session": 0.0,
            },
        )
    )
    respx.get(f"{ORG_METRICS_BASE}/active-users").mock(
        return_value=httpx.Response(
            200,
            json={"start_time": 1000, "end_time": 2000, "active_users": 1},
        )
    )
    for suffix, series in (("dau", dau), ("wau", wau), ("mau", mau)):
        respx.get(f"{ORG_METRICS_BASE}/{suffix}").mock(
            return_value=httpx.Response(
                200,
                json=series
                if series is not None
                else [{"start_time": 1000, "end_time": 2000, "active_users": 1}],
            )
        )


@pytest.mark.asyncio
@respx.mock
async def test_org_consumption_response_parsing(devin_settings):
    respx.get("https://api.devin.ai/v3/organizations/org-test123/consumption/daily").mock(
        return_value=httpx.Response(
            200,
            json={
                "total_acus": 12.5,
                "consumption_by_date": [
                    {
                        "date": 1735689600,
                        "acus": 12.5,
                        "acus_by_product": {"devin": 10.0, "cascade": 2.5, "terminal": 0.0},
                    }
                ],
            },
        )
    )
    service = DevinAnalyticsService(DevinClient(devin_settings))
    result = await service.get_org_consumption_window()
    await service.devin_client.close()
    assert result.total_acus == 12.5
    assert service.consumption_api_available is True


@pytest.mark.asyncio
@respx.mock
async def test_analytics_permission_error(devin_settings):
    respx.get("https://api.devin.ai/v3/organizations/org-test123/consumption/daily").mock(
        return_value=httpx.Response(403, json={"detail": "Forbidden"})
    )
    service = DevinAnalyticsService(DevinClient(devin_settings))
    result = await service.get_org_consumption_window()
    await service.devin_client.close()
    assert result.status_code == 403
    assert service.consumption_api_available is False


@pytest.mark.asyncio
@respx.mock
async def test_analytics_empty_data(devin_settings):
    respx.get("https://api.devin.ai/v3/organizations/org-test123/consumption/daily").mock(
        return_value=httpx.Response(200, json={"total_acus": 0.0, "consumption_by_date": []})
    )
    service = DevinAnalyticsService(DevinClient(devin_settings))
    result = await service.get_org_consumption_window()
    await service.devin_client.close()
    assert result.total_acus == 0.0


def test_local_metrics_remain_honest_without_analytics(db_session):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id="analytics-001",
            github_repository="owner/superset",
            github_issue_number=801,
            github_issue_url="https://github.com/owner/superset/issues/801",
            issue_title="Metrics local",
        )
    )
    repo.update_status(task, TaskStatus.MERGED, merged_at=task.created_at)
    metrics = MetricsService(db_session).compute()
    assert metrics.total_tasks == 1
    assert metrics.merge_rate == 1.0
    assert metrics.devin_org_total_acus is None


@pytest.mark.asyncio
@respx.mock
async def test_metrics_with_analytics_includes_org_total(db_session, devin_settings, monkeypatch):
    monkeypatch.setenv("DEVIN_API_KEY", devin_settings.devin_api_key)
    monkeypatch.setenv("DEVIN_ORG_ID", devin_settings.devin_org_id)
    from app.config import get_settings

    get_settings.cache_clear()

    respx.get("https://api.devin.ai/v3/organizations/org-test123/consumption/daily").mock(
        return_value=httpx.Response(
            200,
            json={"total_acus": 8.0, "consumption_by_date": []},
        )
    )
    mock_org_metrics()
    metrics = await MetricsService(db_session).compute_with_analytics()
    assert metrics.devin_org_total_acus == 8.0
    assert metrics.consumption_api_available is True
    assert metrics.org_metrics_window_days == 30
    assert metrics.devin_org_metrics is not None
    assert metrics.devin_org_metrics.usage.sessions_count == 8


@pytest.mark.asyncio
@respx.mock
async def test_org_metrics_snapshot_uses_peak_not_latest_bucket(devin_settings):
    mock_org_metrics(
        dau=[
            {"start_time": 1000, "end_time": 2000, "active_users": 1},
            {"start_time": 2000, "end_time": 3000, "active_users": 3},
            {"start_time": 3000, "end_time": 4000, "active_users": 0},
        ],
        wau=[
            {"start_time": 1000, "end_time": 3000, "active_users": 4},
            {"start_time": 3000, "end_time": 5000, "active_users": 0},
        ],
        mau=[{"start_time": 1000, "end_time": 9000, "active_users": 5}],
    )
    service = DevinAnalyticsService(DevinClient(devin_settings))
    snapshot = await service.get_org_metrics_snapshot(time_after=1000, time_before=9000)
    await service.devin_client.close()

    assert snapshot is not None
    assert service.org_metrics_available is True
    assert snapshot.window_start == 1000
    assert snapshot.window_end == 9000
    assert snapshot.pull_requests.prs_closed_count == 1
    assert snapshot.sessions.sessions_created_by_origin["api"] == 6
    # The trailing bucket is the in-progress period and reads 0.
    assert (snapshot.peak_dau, snapshot.peak_wau, snapshot.peak_mau) == (3, 4, 5)


@pytest.mark.asyncio
@respx.mock
async def test_org_metrics_snapshot_degrades_on_permission_error(devin_settings):
    mock_org_metrics()
    respx.get(f"{ORG_METRICS_BASE}/sessions").mock(
        return_value=httpx.Response(403, json={"detail": "Forbidden"})
    )
    service = DevinAnalyticsService(DevinClient(devin_settings))
    snapshot = await service.get_org_metrics_snapshot(time_after=1000, time_before=9000)
    await service.devin_client.close()

    assert snapshot is None
    assert service.org_metrics_available is False


@pytest.mark.asyncio
@respx.mock
async def test_org_metrics_requests_send_required_window_params(devin_settings):
    mock_org_metrics()
    service = DevinAnalyticsService(DevinClient(devin_settings))
    await service.get_org_metrics_snapshot(time_after=1000, time_before=9000)
    await service.devin_client.close()

    # /metrics/sessions returns 422 without both bounds, so every call must carry them.
    for call in respx.calls:
        assert call.request.url.params["time_after"] == "1000"
        assert call.request.url.params["time_before"] == "9000"


@pytest.mark.asyncio
async def test_compute_with_analytics_skips_devin_without_org_id(db_session, monkeypatch):
    monkeypatch.delenv("DEVIN_ORG_ID", raising=False)
    monkeypatch.setenv("DEVIN_API_KEY", "cog_test_key")
    from app.config import get_settings

    get_settings.cache_clear()

    metrics = await MetricsService(db_session).compute_with_analytics()
    assert metrics.devin_org_metrics is None
    assert metrics.devin_org_total_acus is None
