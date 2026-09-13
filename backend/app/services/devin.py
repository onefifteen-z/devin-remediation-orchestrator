import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.schemas.devin_session import DevinSessionResponse, parse_devin_session_response

logger = logging.getLogger(__name__)


class DevinAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class DevinAuthError(DevinAPIError):
    pass


class DevinRateLimitError(DevinAPIError):
    pass


@dataclass
class DevinSessionResult:
    session_id: str
    url: str
    status: str
    raw: dict[str, Any]


class DevinClient:
    """Devin V3 API client. See https://docs.devin.ai/api-reference/v3/usage-examples"""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.devin_api_base_url,
                headers={
                    "Authorization": f"Bearer {self.settings.devin_api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    def _org_path(self, suffix: str) -> str:
        return f"/organizations/{self.settings.devin_org_id}{suffix}"

    def _handle_error(self, response: httpx.Response) -> None:
        if response.status_code == 401:
            raise DevinAuthError("Invalid or expired Devin API key", response.status_code)
        if response.status_code == 403:
            raise DevinAuthError("Devin service user lacks required permission", response.status_code)
        if response.status_code == 429:
            raise DevinRateLimitError("Devin API rate limit exceeded", response.status_code)
        if response.status_code >= 400:
            raise DevinAPIError(
                f"Devin API error: {response.status_code}",
                response.status_code,
            )

    def _parse_session(self, data: dict[str, Any]) -> DevinSessionResult:
        return DevinSessionResult(
            session_id=data["session_id"],
            url=data["url"],
            status=data.get("status", "unknown"),
            raw=data,
        )

    async def create_session(
        self,
        prompt: str,
        tags: list[str] | None = None,
        max_acu_limit: int | None = None,
        repos: list[str] | None = None,
    ) -> DevinSessionResult:
        body: dict[str, Any] = {"prompt": prompt}
        if tags:
            body["tags"] = tags
        if max_acu_limit is not None:
            body["max_acu_limit"] = max_acu_limit
        if repos:
            body["repos"] = repos

        client = await self._get_client()
        try:
            response = await client.post(self._org_path("/sessions"), json=body)
        except httpx.TimeoutException:
            raise DevinAPIError("Devin API request timed out") from None

        if response.status_code >= 400:
            self._handle_error(response)

        try:
            data = response.json()
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

        if "session_id" not in data or "url" not in data:
            raise DevinAPIError("Malformed Devin API response")

        logger.info(
            "Devin session created",
            extra={"devin_session_id": data.get("session_id"), "status": data.get("status")},
        )
        return self._parse_session(data)

    async def get_session(self, devin_id: str) -> DevinSessionResponse:
        client = await self._get_client()
        try:
            response = await client.get(self._org_path(f"/sessions/{devin_id}"))
        except httpx.TimeoutException:
            raise DevinAPIError("Devin API request timed out") from None

        if response.status_code >= 400:
            self._handle_error(response)

        try:
            data = response.json()
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

        try:
            session = parse_devin_session_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

        logger.debug(
            "Devin session fetched",
            extra={
                "devin_session_id": session.session_id,
                "status": session.status,
                "acus_consumed": session.acus_consumed,
            },
        )
        return session

    async def send_message(self, devin_id: str, message: str) -> DevinSessionResult:
        client = await self._get_client()
        response = await client.post(
            self._org_path(f"/sessions/{devin_id}/messages"),
            json={"message": message},
        )
        if response.status_code >= 400:
            self._handle_error(response)
        return self._parse_session(response.json())
