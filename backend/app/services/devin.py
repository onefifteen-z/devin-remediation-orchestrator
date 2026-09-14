import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.schemas.devin_consumption import ConsumptionResponse, parse_consumption_response
from app.schemas.devin_automation import (
    AUTOMATION_METADATA_WORKFLOW,
    AutomationResponse,
    parse_automation_list_response,
    parse_automation_response,
)
from app.schemas.devin_insights import SessionInsights, parse_session_insights_list
from app.schemas.devin_metrics import (
    OrgActiveUsersPoint,
    OrgPrMetrics,
    OrgSessionMetrics,
    OrgUsageMetrics,
    parse_org_active_users,
    parse_org_active_users_series,
    parse_org_pr_metrics,
    parse_org_session_metrics,
    parse_org_usage_metrics,
)
from app.schemas.devin_schedule import ScheduleResponse, parse_schedule_response
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

    def _error_message(self, response: httpx.Response) -> str:
        detail: str | None = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                detail = payload.get("detail") or payload.get("title")
        except ValueError:
            detail = response.text[:500] if response.text else None
        message = f"Devin API error: {response.status_code}"
        if detail:
            message = f"{message} — {detail}"
        return message

    def _handle_error(self, response: httpx.Response) -> None:
        message = self._error_message(response)
        if response.status_code == 401:
            raise DevinAuthError(message, response.status_code)
        if response.status_code == 403:
            raise DevinAuthError(message, response.status_code)
        if response.status_code == 429:
            raise DevinRateLimitError(message, response.status_code)
        if response.status_code >= 400:
            raise DevinAPIError(message, response.status_code)

    def _parse_session(self, data: dict[str, Any]) -> DevinSessionResult:
        return DevinSessionResult(
            session_id=data["session_id"],
            url=data["url"],
            status=data.get("status", "unknown"),
            raw=data,
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        max_attempts: int = 3,
    ) -> dict[str, Any]:
        client = await self._get_client()
        last_error: DevinAPIError | None = None
        for attempt in range(max_attempts):
            try:
                response = await client.request(method, path, json=json, params=params)
            except httpx.TimeoutException:
                last_error = DevinAPIError("Devin API request timed out")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise last_error from None

            if response.status_code in {429, 502, 503, 504} and attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (2**attempt))
                continue

            if response.status_code >= 400:
                self._handle_error(response)

            try:
                return response.json()
            except ValueError:
                raise DevinAPIError("Malformed Devin API response") from None

        if last_error:
            raise last_error
        raise DevinAPIError("Devin API request failed")

    async def create_session(
        self,
        prompt: str,
        tags: list[str] | None = None,
        max_acu_limit: int | None = None,
        repos: list[str] | None = None,
        structured_output_schema: dict[str, Any] | None = None,
        structured_output_required: bool = True,
        playbook_id: str | None = None,
    ) -> DevinSessionResult:
        body: dict[str, Any] = {"prompt": prompt}
        if tags:
            body["tags"] = tags
        if max_acu_limit is not None:
            body["max_acu_limit"] = max_acu_limit
        if repos:
            body["repos"] = repos
        if structured_output_schema is not None:
            body["structured_output_schema"] = structured_output_schema
            body["structured_output_required"] = structured_output_required
        if playbook_id:
            body["playbook_id"] = playbook_id

        data = await self._request_json("POST", self._org_path("/sessions"), json=body)

        if "session_id" not in data or "url" not in data:
            raise DevinAPIError("Malformed Devin API response")

        logger.info(
            "Devin session created",
            extra={"devin_session_id": data.get("session_id"), "status": data.get("status")},
        )
        return self._parse_session(data)

    async def get_session(self, devin_id: str) -> DevinSessionResponse:
        data = await self._request_json("GET", self._org_path(f"/sessions/{devin_id}"))
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

    async def list_session_insights(self, limit: int = 100) -> list[SessionInsights]:
        """Fetch insights for every org session in one call, avoiding per-task requests."""
        data = await self._request_json(
            "GET",
            self._org_path("/sessions/insights"),
            params={"limit": limit},
        )
        try:
            return parse_session_insights_list(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def send_message(self, devin_id: str, message: str) -> DevinSessionResult:
        data = await self._request_json(
            "POST",
            self._org_path(f"/sessions/{devin_id}/messages"),
            json={"message": message},
        )
        return self._parse_session(data)

    async def get_session_consumption(
        self,
        session_id: str,
        time_after: int | None = None,
        time_before: int | None = None,
    ) -> ConsumptionResponse:
        """Consumption reporting via the API is Enterprise-plan only.

        On other plans every consumption endpoint answers 200 with an empty
        ledger rather than an error, so callers cannot distinguish "no usage"
        from "not entitled".
        """
        params: dict[str, Any] = {}
        if time_after is not None:
            params["time_after"] = time_after
        if time_before is not None:
            params["time_before"] = time_before
        data = await self._request_json(
            "GET",
            self._org_path(f"/consumption/daily/sessions/{session_id}"),
            params=params or None,
        )
        try:
            return parse_consumption_response(data)
        except Exception:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_consumption_daily(
        self,
        time_after: int | None = None,
        time_before: int | None = None,
    ) -> ConsumptionResponse:
        """Enterprise-plan only; see get_session_consumption.

        Unlike the /metrics endpoints, the time window has no observable effect
        when the org is not entitled.
        """
        params: dict[str, Any] = {}
        if time_after is not None:
            params["time_after"] = time_after
        if time_before is not None:
            params["time_before"] = time_before
        data = await self._request_json(
            "GET",
            self._org_path("/consumption/daily"),
            params=params or None,
        )
        try:
            return parse_consumption_response(data)
        except Exception:
            raise DevinAPIError("Malformed Devin API response") from None

    async def _org_metrics_json(
        self,
        suffix: str,
        time_after: int,
        time_before: int,
    ) -> Any:
        """Metrics endpoints reject missing windows with 422, so both bounds are required."""
        return await self._request_json(
            "GET",
            self._org_path(f"/metrics/{suffix}"),
            params={"time_after": time_after, "time_before": time_before},
        )

    async def get_org_usage_metrics(
        self, time_after: int, time_before: int
    ) -> OrgUsageMetrics:
        data = await self._org_metrics_json("usage", time_after, time_before)
        try:
            return parse_org_usage_metrics(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_pr_metrics(self, time_after: int, time_before: int) -> OrgPrMetrics:
        data = await self._org_metrics_json("prs", time_after, time_before)
        try:
            return parse_org_pr_metrics(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_session_metrics(
        self, time_after: int, time_before: int
    ) -> OrgSessionMetrics:
        data = await self._org_metrics_json("sessions", time_after, time_before)
        try:
            return parse_org_session_metrics(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_active_users(
        self, time_after: int, time_before: int
    ) -> OrgActiveUsersPoint:
        data = await self._org_metrics_json("active-users", time_after, time_before)
        try:
            return parse_org_active_users(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_daily_active_users(
        self, time_after: int, time_before: int
    ) -> list[OrgActiveUsersPoint]:
        data = await self._org_metrics_json("dau", time_after, time_before)
        try:
            return parse_org_active_users_series(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_weekly_active_users(
        self, time_after: int, time_before: int
    ) -> list[OrgActiveUsersPoint]:
        data = await self._org_metrics_json("wau", time_after, time_before)
        try:
            return parse_org_active_users_series(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_org_monthly_active_users(
        self, time_after: int, time_before: int
    ) -> list[OrgActiveUsersPoint]:
        data = await self._org_metrics_json("mau", time_after, time_before)
        try:
            return parse_org_active_users_series(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def create_schedule(self, body: dict[str, Any]) -> ScheduleResponse:
        data = await self._request_json("POST", self._org_path("/schedules"), json=body)
        try:
            return parse_schedule_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def get_schedule(self, schedule_id: str) -> ScheduleResponse:
        data = await self._request_json(
            "GET",
            self._org_path(f"/schedules/{schedule_id}"),
        )
        try:
            return parse_schedule_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def update_schedule(self, schedule_id: str, body: dict[str, Any]) -> ScheduleResponse:
        data = await self._request_json(
            "PATCH",
            self._org_path(f"/schedules/{schedule_id}"),
            json=body,
        )
        try:
            return parse_schedule_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def list_automations(
        self,
        *,
        metadata: dict[str, str] | None = None,
    ) -> list[AutomationResponse]:
        params: dict[str, str] = {}
        if metadata:
            for key, value in metadata.items():
                params[f"metadata.{key}"] = value
        data = await self._request_json("GET", self._org_path("/automations"), params=params or None)
        try:
            return parse_automation_list_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def find_scheduled_intake_automation(self) -> AutomationResponse | None:
        automations = await self.list_automations(
            metadata={"workflow": AUTOMATION_METADATA_WORKFLOW},
        )
        return automations[0] if automations else None

    async def create_automation(self, body: dict[str, Any]) -> AutomationResponse:
        data = await self._request_json("POST", self._org_path("/automations"), json=body)
        try:
            return parse_automation_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None

    async def update_automation(
        self,
        automation_id: str,
        body: dict[str, Any],
    ) -> AutomationResponse:
        data = await self._request_json(
            "PATCH",
            self._org_path(f"/automations/{automation_id}"),
            json=body,
        )
        try:
            return parse_automation_response(data)
        except ValueError:
            raise DevinAPIError("Malformed Devin API response") from None
