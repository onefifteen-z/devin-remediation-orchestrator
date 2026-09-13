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
async def test_list_issues_by_label_filters_pull_requests(github_settings):
    respx.get("https://api.github.com/repos/owner/superset/issues").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "number": 44176,
                    "title": "Bug issue",
                    "html_url": "https://github.com/owner/superset/issues/44176",
                    "labels": [{"name": "devin-remediate"}, {"name": "bug"}],
                },
                {
                    "number": 99,
                    "title": "PR disguised as issue",
                    "html_url": "https://github.com/owner/superset/pull/99",
                    "labels": [{"name": "devin-remediate"}],
                    "pull_request": {},
                },
            ],
        )
    )

    client = GitHubClient(github_settings)
    issues = await client.list_issues_by_label("owner/superset", "devin-remediate")
    await client.close()

    assert len(issues) == 1
    assert issues[0]["number"] == 44176
    assert issues[0]["repository"] == "owner/superset"


@pytest.mark.asyncio
@respx.mock
async def test_list_issues_by_label_api_error(github_settings):
    respx.get("https://api.github.com/repos/owner/superset/issues").mock(
        return_value=httpx.Response(401, json={"message": "Bad credentials"})
    )

    client = GitHubClient(github_settings)
    with pytest.raises(GitHubAPIError):
        await client.list_issues_by_label("owner/superset", "devin-remediate")
    await client.close()
