import asyncio
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.services.devin import DevinAPIError, DevinClient
from app.services.orchestration import RemediationOrchestrator

logger = logging.getLogger(__name__)


class SessionPoller:
    """Background poller for Devin session lifecycle updates."""

    def __init__(
        self,
        settings: Settings,
        session_factory: Callable[[], Session],
        devin_client: DevinClient,
    ):
        self.settings = settings
        self.session_factory = session_factory
        self.devin_client = devin_client
        self._interval = settings.devin_session_poll_interval_seconds
        self._max_failures = settings.devin_poll_max_failures
        self._failure_counts: dict[int, int] = {}
        self._stop = asyncio.Event()
        self._poll_lock = asyncio.Lock()
        self._task: asyncio.Task | None = None

    async def poll_once(self) -> None:
        if self._interval <= 0:
            return

        async with self._poll_lock:
            db = self.session_factory()
            try:
                repo = TaskRepository(db)
                orchestrator = RemediationOrchestrator(
                    db, self.settings, devin_client=self.devin_client
                )

                pollable = repo.list_pollable_tasks()
                for task in pollable:
                    claimed = repo.claim_task_for_polling(task.id)
                    if not claimed:
                        continue
                    try:
                        await orchestrator.sync_task_from_devin(claimed.id)
                        self._failure_counts.pop(claimed.id, None)
                    except DevinAPIError as exc:
                        self._handle_poll_failure(db, claimed.id, exc)

                if self.settings.github_token:
                    for task in repo.list_tasks_pending_ci_sync():
                        await orchestrator.sync_task_ci_from_github(task.id)
            finally:
                db.close()

    def _handle_poll_failure(self, db: Session, task_id: int, exc: DevinAPIError) -> None:
        count = self._failure_counts.get(task_id, 0) + 1
        self._failure_counts[task_id] = count
        logger.warning(
            "Devin session poll failed",
            extra={
                "task_id": task_id,
                "poll_failure_count": count,
                "error": str(exc),
                "status_code": exc.status_code,
            },
        )
        if count >= self._max_failures:
            repo = TaskRepository(db)
            task = repo.get_by_id(task_id)
            if task and task.status not in {
                TaskStatus.MERGED,
                TaskStatus.FAILED,
                TaskStatus.ESCALATED,
            }:
                orchestrator = RemediationOrchestrator(
                    db, self.settings, devin_client=self.devin_client
                )
                orchestrator.transition(
                    task,
                    TaskStatus.ESCALATED,
                    escalation_reason="Repeated Devin session poll failures",
                )
            self._failure_counts.pop(task_id, None)

    async def start(self) -> None:
        if self._interval <= 0:
            logger.info("Session poller disabled (DEVIN_SESSION_POLL_INTERVAL_SECONDS=0)")
            return

        logger.info(
            "Session poller started",
            extra={"poll_interval_seconds": self._interval},
        )
        while not self._stop.is_set():
            try:
                await self.poll_once()
            except Exception:
                logger.exception("Unexpected session poller error")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval)
            except TimeoutError:
                continue

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def start_background(self) -> asyncio.Task:
        self._task = asyncio.create_task(self.start())
        return self._task
