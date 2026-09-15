import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class GitHubAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class GitHubClient:
    """GitHub REST API client for orchestrator-initiated actions."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self.settings.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise GitHubAPIError(
                f"GitHub API error: {response.status_code}",
                response.status_code,
            )

    def _split_repository(self, repository: str) -> tuple[str, str]:
        owner, repo = repository.split("/", 1)
        return owner, repo

    async def list_issues_by_label(self, repository: str, label: str) -> list[dict[str, Any]]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.get(
            f"/repos/{owner}/{repo}/issues",
            params={"labels": label, "state": "open", "per_page": 100},
        )
        if response.status_code >= 400:
            self._handle_error(response)

        issues = response.json()
        return [
            {
                "repository": repository,
                "number": issue["number"],
                "title": issue.get("title", ""),
                "html_url": issue["html_url"],
                "labels": issue.get("labels", []),
            }
            for issue in issues
            if "pull_request" not in issue
        ]

    async def get_issue(self, repository: str, issue_number: int) -> dict[str, Any]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/issues/{issue_number}")
        if response.status_code >= 400:
            self._handle_error(response)
        return response.json()

    async def get_pull_request(self, repository: str, pr_number: int) -> dict[str, Any]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        if response.status_code >= 400:
            self._handle_error(response)
        return response.json()

    async def create_issue_comment(
        self, repository: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        if response.status_code >= 400:
            self._handle_error(response)
        return response.json()

    async def close_issue(self, repository: str, issue_number: int) -> dict[str, Any]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.patch(
            f"/repos/{owner}/{repo}/issues/{issue_number}",
            json={"state": "closed"},
        )
        if response.status_code >= 400:
            self._handle_error(response)
        return response.json()

    async def get_commit_combined_status(self, repository: str, ref: str) -> dict[str, Any]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.get(f"/repos/{owner}/{repo}/commits/{ref}/status")
        if response.status_code >= 400:
            self._handle_error(response)
        return response.json()

    async def list_check_runs_for_ref(self, repository: str, ref: str) -> list[dict[str, Any]]:
        owner, repo = self._split_repository(repository)
        client = await self._get_client()
        response = await client.get(
            f"/repos/{owner}/{repo}/commits/{ref}/check-runs",
            params={"filter": "latest", "per_page": 100},
        )
        if response.status_code >= 400:
            self._handle_error(response)
        data = response.json()
        check_runs = data.get("check_runs", [])
        return check_runs if isinstance(check_runs, list) else []

    async def get_check_runs(self, repository: str, ref: str) -> list[dict[str, Any]]:
        return await self.list_check_runs_for_ref(repository, ref)
