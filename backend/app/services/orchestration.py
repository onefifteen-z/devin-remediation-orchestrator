import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.task import RemediationTask, TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import RemediationEvent, TaskCreate
from app.services.devin import DevinAPIError, DevinClient
from app.services.prompt_builder import build_remediation_prompt, build_session_tags

logger = logging.getLogger(__name__)


class ConcurrencyLimitError(Exception):
    pass


class RemediationOrchestrator:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        devin_client: DevinClient | None = None,
    ):
        self.db = db
        self.settings = settings
        self.repo = TaskRepository(db)
        self.devin_client = devin_client or DevinClient(settings)

    def handle_webhook_event(self, event: RemediationEvent) -> RemediationTask:
        return self.repo.create_task(
            TaskCreate(
                github_delivery_id=event.github_delivery_id,
                github_repository=event.github_repository,
                github_issue_number=event.github_issue_number,
                github_issue_url=event.github_issue_url,
                issue_title=event.issue_title,
                issue_type=event.issue_type,
                max_retries=self.settings.max_retries,
            )
        )

    async def process_task(self, task_id: int) -> None:
        task = self.repo.get_by_id(task_id)
        if not task:
            logger.warning("Task not found", extra={"task_id": task_id})
            return

        if not self.settings.devin_live_enabled:
            logger.info(
                "DEVIN_LIVE_ENABLED=false; task remains at RECEIVED",
                extra={
                    "task_id": task_id,
                    "repository": task.github_repository,
                    "issue_number": task.github_issue_number,
                },
            )
            return

        if self.should_escalate(task):
            self.transition(
                task,
                TaskStatus.ESCALATED,
                escalation_reason="Task exceeded safety boundary before processing",
            )
            return

        claimed_task = self.repo.claim_task_if_received(task_id)
        if not claimed_task:
            latest = self.repo.get_by_id(task_id)
            status = latest.status.value if latest else "unknown"
            logger.info(
                "Task already claimed or no longer RECEIVED",
                extra={"task_id": task_id, "status": status},
            )
            return

        active_count = self.repo.count_active_sessions()
        if active_count >= self.settings.max_active_sessions:
            logger.warning(
                "Concurrency limit reached",
                extra={
                    "task_id": task_id,
                    "active_sessions": active_count,
                    "max_active_sessions": self.settings.max_active_sessions,
                },
            )
            self.transition(
                claimed_task,
                TaskStatus.RECEIVED,
                started_at=None,
            )
            return

        prompt = build_remediation_prompt(claimed_task)
        tags = build_session_tags(claimed_task)

        try:
            session = await self.devin_client.create_session(
                prompt=prompt,
                tags=tags,
                max_acu_limit=self.settings.max_acu_per_task,
            )
            self.transition(
                claimed_task,
                TaskStatus.SESSION_CREATED,
                devin_session_id=session.session_id,
                devin_session_url=session.url,
            )
        except DevinAPIError as exc:
            self.handle_retryable_error(claimed_task, str(exc))

    def transition(self, task: RemediationTask, new_status: TaskStatus, **fields) -> RemediationTask:
        logger.info(
            "Task status transition",
            extra={
                "task_id": task.id,
                "from_status": task.status.value,
                "to_status": new_status.value,
            },
        )
        if new_status in {TaskStatus.MERGED, TaskStatus.FAILED, TaskStatus.ESCALATED}:
            fields.setdefault("completed_at", datetime.now(UTC))
        if new_status == TaskStatus.MERGED:
            fields.setdefault("merged_at", datetime.now(UTC))
        return self.repo.update_status(task, new_status, **fields)

    def increment_retry(self, task: RemediationTask, reason: str) -> RemediationTask:
        new_count = task.retry_count + 1
        if new_count >= task.max_retries:
            return self.transition(
                task,
                TaskStatus.ESCALATED,
                retry_count=new_count,
                escalation_reason=f"Max retries exceeded: {reason}",
            )
        return self.repo.update_task(task, retry_count=new_count, failure_reason=reason)

    def handle_retryable_error(self, task: RemediationTask, reason: str) -> RemediationTask:
        return self.increment_retry(task, reason)

    def should_escalate(self, task: RemediationTask) -> bool:
        if task.retry_count >= task.max_retries:
            return True
        if task.started_at:
            timeout = timedelta(minutes=self.settings.devin_session_timeout_minutes)
            if datetime.now(UTC) - _ensure_aware(task.started_at) > timeout:
                return True
        if (
            self.settings.max_acu_per_task is not None
            and task.acu_used is not None
            and task.acu_used >= self.settings.max_acu_per_task
        ):
            return True
        return False


def _ensure_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
