import httpx
import pytest
import respx

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.devin_session import DevinSessionResponse
from app.schemas.task import TaskCreate
from app.services.devin import DevinClient
from app.services.devin_consumption import DevinConsumptionService
from app.services.orchestration import RemediationOrchestrator
from tests.test_orchestration import FakeDevinClient, _live_settings


@pytest.fixture
def devin_settings():
    return Settings(
        devin_api_key="cog_test_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )


@pytest.mark.asyncio
@respx.mock
async def test_valid_session_consumption_response(devin_settings):
    respx.get(
        "https://api.devin.ai/v3/organizations/org-test123/consumption/daily/sessions/devin-abc123"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"total_acus": 3.2, "consumption_by_date": []},
        )
    )
    client = DevinClient(devin_settings)
    result = await client.get_session_consumption("devin-abc123")
    await client.close()
    assert result.total_acus == 3.2


@pytest.mark.asyncio
async def test_consumption_service_persists_verified_acu(db_session):
    class ConsumptionDevinClient:
        async def get_session_consumption(self, session_id, time_after=None, time_before=None):
            from app.schemas.devin_consumption import ConsumptionResponse

            return ConsumptionResponse(total_acus=5.5, consumption_by_date=[])

    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="consumption-001",
            github_repository="owner/superset",
            github_issue_number=701,
            github_issue_url="https://github.com/owner/superset/issues/701",
            issue_title="Consumption",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.MERGED,
        devin_session_id="devin-consume",
        devin_session_url="https://app.devin.ai/sessions/devin-consume",
        acu_used=0.0,
        acu_source="session_detail",
        acu_verified=False,
    )
    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(),
        devin_client=ConsumptionDevinClient(),
    )
    updated = await orchestrator.sync_final_consumption(task.id)
    assert updated.acu_used == 5.5
    assert updated.acu_source == "consumption_api"
    assert updated.acu_verified is True


@pytest.mark.asyncio
async def test_session_detail_acu_source(db_session):
    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="consumption-002",
            github_repository="owner/superset",
            github_issue_number=702,
            github_issue_url="https://github.com/owner/superset/issues/702",
            issue_title="Session detail ACU",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.RUNNING,
        devin_session_id="devin-detail",
        devin_session_url="https://app.devin.ai/sessions/devin-detail",
    )
    orchestrator = RemediationOrchestrator(db_session, Settings(), devin_client=FakeDevinClient())
    updated = await orchestrator.apply_session_update(
        task,
        DevinSessionResponse(
            session_id="devin-detail",
            url="https://app.devin.ai/sessions/devin-detail",
            status="running",
            acus_consumed=0.0,
        ),
    )
    assert updated.acu_used == 0.0
    assert updated.acu_source == "session_detail"
    assert updated.acu_verified is False


@pytest.mark.asyncio
@respx.mock
async def test_consumption_401_handled_safely(devin_settings):
    respx.get(
        "https://api.devin.ai/v3/organizations/org-test123/consumption/daily/sessions/devin-abc123"
    ).mock(return_value=httpx.Response(401, json={"detail": "Unauthorized"}))
    service = DevinConsumptionService(DevinClient(devin_settings))
    result = await service.get_session_consumption("devin-abc123")
    await service.devin_client.close()
    assert result.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_consumption_403_handled_safely(devin_settings):
    respx.get(
        "https://api.devin.ai/v3/organizations/org-test123/consumption/daily/sessions/devin-abc123"
    ).mock(return_value=httpx.Response(403, json={"detail": "Forbidden"}))
    service = DevinConsumptionService(DevinClient(devin_settings))
    result = await service.get_session_consumption("devin-abc123")
    await service.devin_client.close()
    assert result.status_code == 403
    assert "ViewOrgConsumption" in result.reason


@pytest.mark.asyncio
@respx.mock
async def test_consumption_timeout_handled_safely(devin_settings):
    respx.get(
        "https://api.devin.ai/v3/organizations/org-test123/consumption/daily/sessions/devin-abc123"
    ).mock(side_effect=httpx.TimeoutException("timed out"))
    service = DevinConsumptionService(DevinClient(devin_settings))
    result = await service.get_session_consumption("devin-abc123")
    await service.devin_client.close()
    assert "failed" in result.reason.lower()


@pytest.mark.asyncio
@respx.mock
async def test_consumption_malformed_response_handled_safely(devin_settings):
    respx.get(
        "https://api.devin.ai/v3/organizations/org-test123/consumption/daily/sessions/devin-abc123"
    ).mock(return_value=httpx.Response(200, json={"unexpected": True}))
    service = DevinConsumptionService(DevinClient(devin_settings))
    result = await service.get_session_consumption("devin-abc123")
    await service.devin_client.close()
    assert "failed" in result.reason.lower()


@pytest.mark.asyncio
async def test_merged_task_receives_final_consumption_sync(db_session):
    class ConsumptionDevinClient:
        async def get_session_consumption(self, session_id, time_after=None, time_before=None):
            from app.schemas.devin_consumption import ConsumptionResponse

            return ConsumptionResponse(total_acus=2.1, consumption_by_date=[])

    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="consumption-003",
            github_repository="owner/superset",
            github_issue_number=703,
            github_issue_url="https://github.com/owner/superset/issues/703",
            issue_title="Merged sync",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.MERGED,
        devin_session_id="devin-merged",
        devin_session_url="https://app.devin.ai/sessions/devin-merged",
    )
    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(),
        devin_client=ConsumptionDevinClient(),
    )
    updated = await orchestrator.sync_final_consumption(task.id)
    refreshed = updated or TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.status == TaskStatus.MERGED
    assert refreshed.acu_used == 2.1
    assert refreshed.acu_verified is True


@pytest.mark.asyncio
async def test_consumption_failure_does_not_regress_merged_status(db_session):
    class FailingConsumptionClient:
        async def get_session_consumption(self, session_id, time_after=None, time_before=None):
            from app.schemas.devin_consumption import ConsumptionUnavailable

            return ConsumptionUnavailable(reason="Unavailable", status_code=403)

    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="consumption-004",
            github_repository="owner/superset",
            github_issue_number=704,
            github_issue_url="https://github.com/owner/superset/issues/704",
            issue_title="Merged stays merged",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.MERGED,
        devin_session_id="devin-merged-2",
        devin_session_url="https://app.devin.ai/sessions/devin-merged-2",
    )
    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(),
        devin_client=FailingConsumptionClient(),
    )
    await orchestrator.sync_final_consumption(task.id)
    refreshed = TaskRepository(db_session).get_by_id(task.id)
    assert refreshed.status == TaskStatus.MERGED
    assert refreshed.acu_source == "unavailable"


@pytest.mark.asyncio
async def test_no_fake_acu_generated(db_session):
    class UnavailableClient:
        async def get_session_consumption(self, session_id, time_after=None, time_before=None):
            from app.schemas.devin_consumption import ConsumptionUnavailable

            return ConsumptionUnavailable(reason="Unavailable", status_code=403)

    task = TaskRepository(db_session).create_task(
        TaskCreate(
            github_delivery_id="consumption-005",
            github_repository="owner/superset",
            github_issue_number=705,
            github_issue_url="https://github.com/owner/superset/issues/705",
            issue_title="No fake ACU",
        )
    )
    task = TaskRepository(db_session).update_status(
        task,
        TaskStatus.RUNNING,
        devin_session_id="devin-none",
        devin_session_url="https://app.devin.ai/sessions/devin-none",
        acu_used=None,
    )
    orchestrator = RemediationOrchestrator(
        db_session,
        Settings(),
        devin_client=UnavailableClient(),
    )
    updated = await orchestrator.sync_final_consumption(task.id)
    assert updated.acu_used is None
