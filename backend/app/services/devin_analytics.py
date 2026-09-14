import asyncio
import logging

from app.schemas.devin_consumption import ConsumptionResponse, ConsumptionUnavailable
from app.schemas.devin_metrics import OrgMetricsSnapshot, peak_active_users
from app.services.devin import DevinAPIError, DevinAuthError, DevinClient, DevinRateLimitError

logger = logging.getLogger(__name__)


class DevinAnalyticsService:
    def __init__(self, devin_client: DevinClient):
        self.devin_client = devin_client
        self._last_available: bool | None = None
        self._org_metrics_available: bool | None = None

    @property
    def consumption_api_available(self) -> bool | None:
        return self._last_available

    @property
    def org_metrics_available(self) -> bool | None:
        return self._org_metrics_available

    async def get_org_metrics_snapshot(
        self,
        time_after: int,
        time_before: int,
    ) -> OrgMetricsSnapshot | None:
        """Fetch every org metrics endpoint concurrently for one window.

        Seven sequential requests would dominate the /api/metrics response time,
        so they are gathered instead.
        """
        try:
            usage, prs, sessions, active_users, dau, wau, mau = await asyncio.gather(
                self.devin_client.get_org_usage_metrics(time_after, time_before),
                self.devin_client.get_org_pr_metrics(time_after, time_before),
                self.devin_client.get_org_session_metrics(time_after, time_before),
                self.devin_client.get_org_active_users(time_after, time_before),
                self.devin_client.get_org_daily_active_users(time_after, time_before),
                self.devin_client.get_org_weekly_active_users(time_after, time_before),
                self.devin_client.get_org_monthly_active_users(time_after, time_before),
            )
        except DevinAPIError as exc:
            self._org_metrics_available = False
            logger.warning(
                "Organization metrics request failed",
                extra={"error": str(exc), "status_code": exc.status_code},
            )
            return None

        self._org_metrics_available = True
        return OrgMetricsSnapshot(
            window_start=time_after,
            window_end=time_before,
            usage=usage,
            pull_requests=prs,
            sessions=sessions,
            active_users=active_users.active_users,
            peak_dau=peak_active_users(dau),
            peak_wau=peak_active_users(wau),
            peak_mau=peak_active_users(mau),
        )

    async def get_org_consumption_window(
        self,
        time_after: int | None = None,
        time_before: int | None = None,
    ) -> ConsumptionResponse | ConsumptionUnavailable:
        try:
            result = await self.devin_client.get_org_consumption_daily(
                time_after=time_after,
                time_before=time_before,
            )
            self._last_available = True
            return result
        except DevinAuthError as exc:
            self._last_available = False
            reason = (
                "Organization analytics unavailable because the service user lacks "
                "ViewOrgConsumption permission."
                if exc.status_code == 403
                else "Organization analytics authentication failed."
            )
            logger.warning(
                "Organization consumption unavailable",
                extra={"status_code": exc.status_code},
            )
            return ConsumptionUnavailable(reason=reason, status_code=exc.status_code)
        except DevinRateLimitError as exc:
            self._last_available = False
            return ConsumptionUnavailable(
                reason="Organization analytics rate limited.",
                status_code=exc.status_code,
            )
        except DevinAPIError as exc:
            self._last_available = False
            logger.warning("Organization consumption request failed", extra={"error": str(exc)})
            return ConsumptionUnavailable(
                reason="Organization analytics request failed.",
                status_code=exc.status_code,
            )
