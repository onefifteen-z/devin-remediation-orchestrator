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
    metrics = await MetricsService(db_session).compute_with_analytics()
    assert metrics.devin_org_total_acus == 8.0
    assert metrics.consumption_api_available is True
