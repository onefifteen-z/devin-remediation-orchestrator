import logging

from app.schemas.devin_consumption import ConsumptionResponse, ConsumptionUnavailable
from app.services.devin import DevinAPIError, DevinAuthError, DevinClient, DevinRateLimitError

logger = logging.getLogger(__name__)


class DevinAnalyticsService:
    def __init__(self, devin_client: DevinClient):
        self.devin_client = devin_client
        self._last_available: bool | None = None

    @property
    def consumption_api_available(self) -> bool | None:
        return self._last_available

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
