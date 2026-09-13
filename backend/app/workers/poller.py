import logging

from app.services.devin import DevinClient
from app.services.orchestration import RemediationOrchestrator

logger = logging.getLogger(__name__)


class SessionPoller:
    """Skeleton for Phase 2 session lifecycle polling."""

    def __init__(self, orchestrator: RemediationOrchestrator, devin_client: DevinClient):
        self.orchestrator = orchestrator
        self.devin_client = devin_client

    async def poll_once(self) -> None:
        # TODO: Phase 2 — poll active sessions via DevinClient.get_session,
        # detect PR creation, CI status, and feed orchestrator transitions.
        logger.debug("SessionPoller.poll_once is a Phase 2 stub")

    async def start(self) -> None:
        # TODO: Phase 2 — background polling loop with backoff
        logger.info("SessionPoller.start is a Phase 2 stub")
