import httpx
import pytest
import respx

from app.config import Settings
from app.services.devin import DevinAPIError, DevinAuthError, DevinClient


@pytest.fixture
def devin_settings():
    return Settings(
        devin_api_key="cog_test_key",
        devin_org_id="org-test123",
        devin_api_base_url="https://api.devin.ai/v3",
    )


@pytest.mark.asyncio
@respx.mock
async def test_create_session_success(devin_settings):
    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "devin-abc123",
                "url": "https://app.devin.ai/sessions/devin-abc123",
                "status": "running",
            },
        )
    )

    client = DevinClient(devin_settings)
    result = await client.create_session(
        prompt="Fix the bug",
        tags=["source=github"],
        max_acu_limit=10,
    )
    await client.close()

    assert result.session_id == "devin-abc123"
    assert result.status == "running"


@pytest.mark.asyncio
@respx.mock
async def test_get_session_success(devin_settings):
    respx.get("https://api.devin.ai/v3/organizations/org-test123/sessions/devin-abc123").mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "devin-abc123",
                "url": "https://app.devin.ai/sessions/devin-abc123",
                "status": "exit",
            },
        )
    )

    client = DevinClient(devin_settings)
    result = await client.get_session("devin-abc123")
    await client.close()

    assert result.status == "exit"


@pytest.mark.asyncio
@respx.mock
async def test_send_message_success(devin_settings):
    respx.post(
        "https://api.devin.ai/v3/organizations/org-test123/sessions/devin-abc123/messages"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "session_id": "devin-abc123",
                "url": "https://app.devin.ai/sessions/devin-abc123",
                "status": "running",
            },
        )
    )

    client = DevinClient(devin_settings)
    result = await client.send_message("devin-abc123", "CI failed, please fix")
    await client.close()

    assert result.session_id == "devin-abc123"


@pytest.mark.asyncio
@respx.mock
async def test_auth_error(devin_settings):
    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(401, json={"detail": "Unauthorized"})
    )

    client = DevinClient(devin_settings)
    with pytest.raises(DevinAuthError):
        await client.create_session(prompt="test")
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_api_error(devin_settings):
    respx.post("https://api.devin.ai/v3/organizations/org-test123/sessions").mock(
        return_value=httpx.Response(500, json={"detail": "Server error"})
    )

    client = DevinClient(devin_settings)
    with pytest.raises(DevinAPIError):
        await client.create_session(prompt="test")
    await client.close()
