import logging

from app.schemas.devin_consumption import ConsumptionResponse, ConsumptionUnavailable
from app.services.devin import DevinAPIError, DevinAuthError, DevinClient, DevinRateLimitError

logger = logging.getLogger(__name__)


class DevinConsumptionService:
    def __init__(self, devin_client: DevinClient):
        self.devin_client = devin_client

    async def get_session_consumption(
        self,
        session_id: str,
        time_after: int | None = None,
        time_before: int | None = None,
    ) -> ConsumptionResponse | ConsumptionUnavailable:
        try:
            return await self.devin_client.get_session_consumption(
                session_id,
                time_after=time_after,
                time_before=time_before,
            )
        except DevinAuthError as exc:
            reason = (
                "Consumption API unavailable because the service user lacks "
                "ViewOrgConsumption permission."
                if exc.status_code == 403
                else "Consumption API authentication failed."
            )
            logger.warning(
                "Session consumption unavailable",
                extra={"session_id": session_id, "status_code": exc.status_code},
            )
            return ConsumptionUnavailable(reason=reason, status_code=exc.status_code)
        except DevinRateLimitError as exc:
            return ConsumptionUnavailable(
                reason="Consumption API rate limited.",
                status_code=exc.status_code,
            )
        except DevinAPIError as exc:
            logger.warning(
                "Session consumption request failed",
                extra={"session_id": session_id, "error": str(exc)},
            )
            return ConsumptionUnavailable(
                reason="Consumption API request failed.",
                status_code=exc.status_code,
            )
