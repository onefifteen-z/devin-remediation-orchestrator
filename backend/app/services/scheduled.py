import logging
from datetime import UTC, datetime

from app.config import Settings
from app.services.devin import DevinAPIError, DevinClient

logger = logging.getLogger(__name__)

SCHEDULE_TITLE = "Remediation intake triage"


def build_schedule_prompt(settings: Settings) -> str:
    intake_url = settings.orchestrator_public_url.rstrip("/") + "/api/scheduled/intake"
    token_clause = ""
    if settings.scheduled_intake_token:
        token_clause = (
            f'\nUse header: Authorization: Bearer {settings.scheduled_intake_token}'
        )
    return f"""Review configured repositories for open issues labeled `{settings.scheduled_label}`.

Call the orchestrator intake endpoint to enqueue new remediation candidates:
POST {intake_url}{token_clause}

Do not modify repository code. Report a concise triage summary via structured output:
- issues scanned
- new remediation candidates enqueued
- issues skipped because remediation already exists
- any blockers encountered
"""


class ScheduledRemediationService:
    def __init__(self, settings: Settings, devin_client: DevinClient):
        self.settings = settings
        self.devin_client = devin_client

    async def ensure_schedule(self) -> str | None:
        if not self.settings.devin_scheduled_enabled:
            logger.info("Scheduled Devin disabled (DEVIN_SCHEDULED_ENABLED=false)")
            return None

        if not self.settings.orchestrator_public_url:
            logger.warning(
                "Scheduled Devin enabled but ORCHESTRATOR_PUBLIC_URL is not configured"
            )
            return None

        body = {
            "title": SCHEDULE_TITLE,
            "prompt": build_schedule_prompt(self.settings),
            "schedule_type": "recurring",
            "frequency": self.settings.devin_schedule_cron,
            "tags": ["workflow=scheduled-intake", "environment=take-home"],
            "enabled": True,
        }
        if self.settings.devin_remediation_playbook_id:
            body["playbook_id"] = self.settings.devin_remediation_playbook_id

        try:
            if self.settings.devin_schedule_id:
                schedule = await self.devin_client.update_schedule(
                    self.settings.devin_schedule_id,
                    body,
                )
            else:
                schedule = await self.devin_client.create_schedule(body)
        except DevinAPIError as exc:
            logger.warning(
                "Failed to ensure Devin schedule",
                extra={"error": str(exc), "status_code": exc.status_code},
            )
            return None

        logger.info(
            "Devin schedule ensured",
            extra={
                "schedule_id": schedule.schedule_id,
                "frequency": schedule.frequency,
                "run_time": datetime.now(UTC).isoformat(),
            },
        )
        return schedule.schedule_id
