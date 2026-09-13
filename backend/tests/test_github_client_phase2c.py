import httpx
import pytest
import respx

from app.config import Settings
from app.services.github import GitHubAPIError, GitHubClient


@pytest.fixture
def github_settings():
    return Settings(github_token="ghp_test_token")


@pytest.mark.asyncio
@respx.mock
async def test_create_issue_comment_success(github_settings):
    respx.post(
        "https://api.github.com/repos/owner/superset/issues/44176/comments"
    ).mock(return_value=httpx.Response(201, json={"id": 1, "body": "Remediation completed."}))

    client = GitHubClient(github_settings)
    result = await client.create_issue_comment(
        "owner/superset", 44176, "Remediation completed."
    )
    await client.close()

    assert result["id"] == 1


@pytest.mark.asyncio
@respx.mock
async def test_create_issue_comment_failure(github_settings):
    respx.post(
        "https://api.github.com/repos/owner/superset/issues/44176/comments"
    ).mock(return_value=httpx.Response(403, json={"message": "Forbidden"}))

    client = GitHubClient(github_settings)
    with pytest.raises(GitHubAPIError) as exc_info:
        await client.create_issue_comment("owner/superset", 44176, "test")
    await client.close()

    assert "403" in str(exc_info.value)
    assert "ghp_test_token" not in str(exc_info.value)


@pytest.mark.asyncio
@respx.mock
async def test_close_issue_success(github_settings):
    respx.patch("https://api.github.com/repos/owner/superset/issues/44176").mock(
        return_value=httpx.Response(200, json={"number": 44176, "state": "closed"})
    )

    client = GitHubClient(github_settings)
    result = await client.close_issue("owner/superset", 44176)
    await client.close()

    assert result["state"] == "closed"


@pytest.mark.asyncio
@respx.mock
async def test_close_issue_failure(github_settings):
    respx.patch("https://api.github.com/repos/owner/superset/issues/44176").mock(
        return_value=httpx.Response(500, json={"message": "Server error"})
    )

    client = GitHubClient(github_settings)
    with pytest.raises(GitHubAPIError):
        await client.close_issue("owner/superset", 44176)
    await client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_pull_request(github_settings):
    respx.get("https://api.github.com/repos/owner/superset/pulls/123").mock(
        return_value=httpx.Response(
            200,
            json={
                "number": 123,
                "html_url": "https://github.com/owner/superset/pull/123",
                "state": "closed",
                "merged": True,
            },
        )
    )

    client = GitHubClient(github_settings)
    result = await client.get_pull_request("owner/superset", 123)
    await client.close()

    assert result["merged"] is True


@pytest.mark.asyncio
@respx.mock
async def test_get_issue(github_settings):
    respx.get("https://api.github.com/repos/owner/superset/issues/44176").mock(
        return_value=httpx.Response(200, json={"number": 44176, "state": "open"})
    )

    client = GitHubClient(github_settings)
    result = await client.get_issue("owner/superset", 44176)
    await client.close()

    assert result["state"] == "open"
