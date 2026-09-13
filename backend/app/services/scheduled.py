import logging
from datetime import UTC, datetime

from app.config import Settings
from app.schemas.devin_automation import build_scheduled_intake_automation_body
from app.services.devin import DevinAPIError, DevinClient

logger = logging.getLogger(__name__)

SCHEDULE_NAME = "Remediation intake triage"


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


def build_automation_body(settings: Settings, *, include_playbook: bool = True) -> dict:
    playbook_id = settings.devin_remediation_playbook_id or None
    if not include_playbook:
        playbook_id = None
    return build_scheduled_intake_automation_body(
        name=SCHEDULE_NAME,
        prompt=build_schedule_prompt(settings),
        cron=settings.devin_schedule_cron,
        playbook_id=playbook_id,
        enabled=True,
    )


class ScheduledRemediationService:
    def __init__(self, settings: Settings, devin_client: DevinClient):
        self.settings = settings
        self.devin_client = devin_client

    async def _resolve_automation_id(self) -> str | None:
        if self.settings.devin_automation_id:
            return self.settings.devin_automation_id

        existing = await self.devin_client.find_scheduled_intake_automation()
        return existing.automation_id if existing else None

    async def ensure_schedule(self) -> str | None:
        if not self.settings.devin_scheduled_enabled:
            logger.info("Scheduled Devin disabled (DEVIN_SCHEDULED_ENABLED=false)")
            return None

        if not self.settings.orchestrator_public_url:
            logger.warning(
                "Scheduled Devin enabled but ORCHESTRATOR_PUBLIC_URL is not configured"
            )
            return None

        try:
            automation_id = await self._resolve_automation_id()
            automation = await self._save_automation(automation_id)
        except DevinAPIError as exc:
            logger.warning(
                "Failed to ensure Devin scheduled automation",
                extra={"error": str(exc), "status_code": exc.status_code},
            )
            return None

        logger.info(
            "Devin scheduled automation ensured",
            extra={
                "automation_id": automation.automation_id,
                "name": automation.name,
                "cron": self.settings.devin_schedule_cron,
                "run_time": datetime.now(UTC).isoformat(),
            },
        )
        if not self.settings.devin_automation_id:
            logger.info(
                "Set DEVIN_AUTOMATION_ID=%s to pin this automation for idempotent updates",
                automation.automation_id,
            )
        return automation.automation_id

    async def _save_automation(self, automation_id: str | None):
        bodies = [build_automation_body(self.settings)]
        if self.settings.devin_remediation_playbook_id:
            bodies.append(build_automation_body(self.settings, include_playbook=False))

        last_error: DevinAPIError | None = None
        for index, body in enumerate(bodies):
            try:
                if automation_id:
                    return await self.devin_client.update_automation(automation_id, body)
                return await self.devin_client.create_automation(body)
            except DevinAPIError as exc:
                last_error = exc
                if index == 0 and "unknown playbook" in str(exc).lower():
                    logger.warning(
                        "Devin rejected configured playbook for scheduled automation; retrying without playbook",
                        extra={"playbook_id": self.settings.devin_remediation_playbook_id},
                    )
                    continue
                raise

        if last_error:
            raise last_error
        raise DevinAPIError("Failed to save scheduled automation")
