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
    """GitHub REST API client skeleton. Full implementation in Phase 2."""

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

    async def get_issue(self, repository: str, issue_number: int) -> dict[str, Any]:
        # TODO: Phase 2 — implement issue fetch
        raise NotImplementedError("GitHub get_issue not implemented in Phase 1")

    async def get_pull_request(self, repository: str, pr_number: int) -> dict[str, Any]:
        # TODO: Phase 2 — implement PR fetch
        raise NotImplementedError("GitHub get_pull_request not implemented in Phase 1")

    async def get_check_runs(self, repository: str, ref: str) -> list[dict[str, Any]]:
        # TODO: Phase 2 — implement CI check run inspection
        raise NotImplementedError("GitHub get_check_runs not implemented in Phase 1")

    async def create_issue_comment(
        self, repository: str, issue_number: int, body: str
    ) -> dict[str, Any]:
        # TODO: Phase 2 — implement issue comment
        raise NotImplementedError("GitHub create_issue_comment not implemented in Phase 1")
