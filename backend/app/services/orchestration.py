import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.task import POLLABLE_STATUSES, RemediationTask, TaskStatus
from app.repositories.tasks import (
    DuplicateDeliveryError,
    IssueAlreadyTrackedError,
    TaskRepository,
)
from app.schemas.devin_session import DevinSessionResponse
from app.schemas.remediation import RemediationCreateRequest, RemediationResponse
from app.schemas.scan import ScanResult
from app.schemas.task import RemediationEvent, TaskCreate, TaskResponse
from app.services.devin import DevinAPIError, DevinClient
from app.repositories.webhook_deliveries import WebhookDeliveryRepository
from app.schemas.github_events import PullRequestEvent, extract_issue_type
from app.services.github import GitHubClient
from app.services.github_events import find_task_for_pr
from app.services.prompt_builder import build_remediation_prompt, build_session_tags
from app.services.task_classification import trigger_source_from_event_source
from app.services.session_lifecycle import (
    extract_devin_audit_fields,
    extract_primary_pull_request,
    is_valid_status_transition,
    map_devin_session_to_task_status,
    resolve_exit_escalation_reason,
    resolve_exit_failure_reason,
)

logger = logging.getLogger(__name__)


class ConcurrencyLimitError(Exception):
    pass


def _issue_key(repository: str, issue_number: int) -> str:
    return f"{repository}#{issue_number}"


def _normalize_api_request(request: RemediationCreateRequest) -> RemediationEvent:
    return RemediationEvent(
        github_delivery_id=f"api:{request.repository}:{request.issue_number}",
        source="api",
        github_repository=request.repository,
        github_issue_number=request.issue_number,
        github_issue_url=request.issue_url,
        issue_title=f"Issue #{request.issue_number}",
        issue_type=request.issue_type,
    )


def _live_mode_message(live_enabled: bool, task: RemediationTask) -> str:
    if not live_enabled:
        return "Live Devin execution is disabled (DEVIN_LIVE_ENABLED=false)"
    if task.devin_session_id:
        return "Devin session created successfully"
    if task.failure_reason:
        return f"Devin session creation failed: {task.failure_reason}"
    return "Task processed"


def _is_active_devin_status(status: str) -> bool:
    return status.lower() in {"new", "claimed", "running", "resuming"}


class RemediationOrchestrator:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        devin_client: DevinClient | None = None,
        github_client: GitHubClient | None = None,
    ):
        self.db = db
        self.settings = settings
        self.repo = TaskRepository(db)
        self.webhook_repo = WebhookDeliveryRepository(db)
        self.devin_client = devin_client or DevinClient(settings)
        self.github_client = github_client or GitHubClient(settings)

    def ensure_task_for_issue(self, event: RemediationEvent) -> tuple[RemediationTask, str]:
        existing = self.repo.get_by_issue(
            event.github_repository, event.github_issue_number
        )
        if existing:
            return existing, "skipped"

        try:
            task = self.repo.create_task(
                TaskCreate(
                    github_delivery_id=event.github_delivery_id,
                    github_repository=event.github_repository,
                    github_issue_number=event.github_issue_number,
                    github_issue_url=event.github_issue_url,
                    issue_title=event.issue_title,
                    issue_type=event.issue_type,
                    trigger_source=trigger_source_from_event_source(event.source),
                    max_retries=self.settings.max_retries,
                )
            )
            return task, "created"
        except IssueAlreadyTrackedError as exc:
            return exc.existing_task, "skipped"
        except DuplicateDeliveryError as exc:
            return exc.existing_task, "skipped"

    def handle_webhook_event(self, event: RemediationEvent) -> tuple[RemediationTask, str]:
        return self.ensure_task_for_issue(event)

    async def create_remediation(self, request: RemediationCreateRequest) -> RemediationResponse:
        event = _normalize_api_request(request)
        task, outcome = self.ensure_task_for_issue(event)
        await self.process_task(task.id, reraise_devin_errors=True)
        refreshed = self.repo.get_by_id(task.id)
        if refreshed is None:
            raise RuntimeError(f"Task {task.id} not found after processing")
        return RemediationResponse(
            outcome=outcome,
            devin_live_enabled=self.settings.devin_live_enabled,
            message=_live_mode_message(self.settings.devin_live_enabled, refreshed),
            task=TaskResponse.from_orm_task(refreshed),
        )

    async def scan_labeled_issues(self) -> ScanResult:
        repositories = self.settings.github_scan_repositories_list()
        label = self.settings.remediate_label
        result = ScanResult()

        for repository in repositories:
            issues = await self.github_client.list_issues_by_label(repository, label)
            for issue in issues:
                result.scanned += 1
                event = RemediationEvent(
                    github_delivery_id=f"manual:{repository}:{issue['number']}",
                    source="scan",
                    github_repository=repository,
                    github_issue_number=issue["number"],
                    github_issue_url=issue["html_url"],
                    issue_title=issue["title"],
                    issue_type=extract_issue_type(issue.get("labels", []), label),
                )
                task, status = self.ensure_task_for_issue(event)
                if status == "created":
                    result.created += 1
                    result.created_task_ids.append(task.id)
                else:
                    result.skipped += 1
                    result.skipped_issues.append(
                        _issue_key(repository, issue["number"])
                    )

        return result

    async def process_task(self, task_id: int, *, reraise_devin_errors: bool = False) -> None:
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
            self.repo.update_task(claimed_task, started_at=None)
            return

        prompt = build_remediation_prompt(claimed_task)
        tags = build_session_tags(claimed_task)

        try:
            session = await self.devin_client.create_session(
                prompt=prompt,
                tags=tags,
                repos=[claimed_task.github_repository],
                max_acu_limit=self.settings.max_acu_per_task,
            )
            session_created = self.transition(
                claimed_task,
                TaskStatus.SESSION_CREATED,
                devin_session_id=session.session_id,
                devin_session_url=session.url,
            )
            if _is_active_devin_status(session.status):
                self.transition(session_created, TaskStatus.RUNNING)
        except DevinAPIError as exc:
            self.repo.update_task(claimed_task, started_at=None)
            self.handle_retryable_error(claimed_task, str(exc))
            if reraise_devin_errors:
                raise

    async def sync_task_from_devin(self, task_id: int) -> None:
        task = self.repo.get_by_id(task_id)
        if not task:
            logger.warning("Task not found for session sync", extra={"task_id": task_id})
            return

        if not task.devin_session_id:
            return

        if task.status not in POLLABLE_STATUSES:
            return

        session = await self.devin_client.get_session(task.devin_session_id)
        self.apply_session_update(task, session)

    def apply_session_update(
        self, task: RemediationTask, session: DevinSessionResponse
    ) -> RemediationTask:
        previous_status = task.status
        pr = extract_primary_pull_request(session.pull_requests)

        field_updates: dict = extract_devin_audit_fields(session)
        if session.acus_consumed is not None:
            field_updates["acu_used"] = session.acus_consumed
        if pr is not None:
            field_updates["pr_url"] = pr[0]
            field_updates["pr_state"] = pr[1]
        if session.url and session.url != task.devin_session_url:
            field_updates["devin_session_url"] = session.url

        target_status = map_devin_session_to_task_status(task, session)

        if target_status is None:
            updated = self.repo.update_task(task, **field_updates)
            self._log_session_sync(updated, previous_status, previous_status, pr)
            return updated

        transition_fields = dict(field_updates)
        failure_reason = resolve_exit_failure_reason(session, pr, target_status)
        if failure_reason:
            transition_fields["failure_reason"] = failure_reason
        escalation_reason = resolve_exit_escalation_reason(session, target_status)
        if escalation_reason:
            transition_fields["escalation_reason"] = escalation_reason

        updated = self.transition(task, target_status, **transition_fields)
        self._log_session_sync(updated, previous_status, target_status, pr)
        return updated

    def _log_session_sync(
        self,
        task: RemediationTask,
        previous_status: TaskStatus,
        new_status: TaskStatus,
        pr: tuple[str, str | None] | None,
    ) -> None:
        logger.info(
            "Task session sync",
            extra={
                "task_id": task.id,
                "github_repository": task.github_repository,
                "issue_number": task.github_issue_number,
                "devin_session_id": task.devin_session_id,
                "previous_status": previous_status.value,
                "new_status": new_status.value,
                "pr_url": task.pr_url,
                "acu_used": task.acu_used,
                "pr_state": task.pr_state if pr else None,
            },
        )

    def handle_pull_request_event(self, event: PullRequestEvent) -> tuple[str, int | None]:
        task = find_task_for_pr(
            self.repo,
            event.repository,
            event.pr_url,
            event.pr_number,
        )
        if task is None:
            logger.info(
                "github_event_received",
                extra={
                    "event": event.event_type,
                    "action": event.action,
                    "delivery_id": event.delivery_id,
                    "repository": event.repository,
                    "pr_url": event.pr_url,
                    "task_id": None,
                    "merged": event.merged,
                    "outcome": "ignored_no_task",
                },
            )
            return "ignored", None

        self._log_github_pr_event(event, task)

        if event.action in {"opened", "reopened"}:
            return self._handle_pr_opened(task, event), task.id
        if event.action == "synchronize":
            return self._handle_pr_synchronize(task, event), task.id
        if event.action == "closed":
            if event.merged:
                return self._handle_pr_merged(task, event), task.id
            return self._handle_pr_closed_without_merge(task, event), task.id

        self.repo.update_task(
            task,
            pr_url=event.pr_url,
            pr_state=event.pr_state,
        )
        return "processed", task.id

    def _log_github_pr_event(self, event: PullRequestEvent, task: RemediationTask) -> None:
        logger.info(
            "github_event_received",
            extra={
                "event": event.event_type,
                "action": event.action,
                "delivery_id": event.delivery_id,
                "repository": event.repository,
                "pr_url": event.pr_url,
                "task_id": task.id,
                "merged": event.merged,
            },
        )

    def _handle_pr_opened(self, task: RemediationTask, event: PullRequestEvent) -> str:
        fields = {"pr_url": event.pr_url, "pr_state": event.pr_state}
        if is_valid_status_transition(task.status, TaskStatus.PR_OPENED):
            self.transition(task, TaskStatus.PR_OPENED, **fields)
        else:
            self.repo.update_task(task, **fields)
        return "processed"

    def _handle_pr_synchronize(self, task: RemediationTask, event: PullRequestEvent) -> str:
        self.repo.update_task(
            task,
            pr_url=event.pr_url,
            pr_state=event.pr_state,
        )
        return "processed"

    def _handle_pr_closed_without_merge(
        self, task: RemediationTask, event: PullRequestEvent
    ) -> str:
        fields = {
            "pr_url": event.pr_url,
            "pr_state": event.pr_state,
            "escalation_reason": "Pull request closed without merge.",
        }
        if is_valid_status_transition(task.status, TaskStatus.ESCALATED):
            self.transition(task, TaskStatus.ESCALATED, **fields)
        else:
            self.repo.update_task(task, **fields)
        return "processed"

    def _handle_pr_merged(self, task: RemediationTask, event: PullRequestEvent) -> str:
        if task.status == TaskStatus.MERGED:
            self.repo.update_task(
                task,
                pr_url=event.pr_url,
                pr_state=event.pr_state,
            )
            return "processed"

        merged_at = event.merged_at or datetime.now(UTC)
        fields = {
            "pr_url": event.pr_url,
            "pr_state": event.pr_state,
            "merged_at": merged_at,
            "completed_at": merged_at,
        }
        if is_valid_status_transition(task.status, TaskStatus.MERGED):
            self.transition(task, TaskStatus.MERGED, **fields)
        else:
            self.repo.update_task(task, status=TaskStatus.MERGED, **fields)
        return "merged"

    async def post_merge_github_actions(self, task_id: int) -> None:
        task = self.repo.get_by_id(task_id)
        if not task or task.status != TaskStatus.MERGED:
            return
        if not self.settings.github_token:
            logger.info(
                "Skipping post-merge GitHub actions; GITHUB_TOKEN not configured",
                extra={"task_id": task_id},
            )
            return
        if task.merge_notification_sent:
            return

        comment_body = self._build_merge_comment(task)
        try:
            await self.github_client.create_issue_comment(
                task.github_repository,
                task.github_issue_number,
                comment_body,
            )
            self.repo.update_task(task, merge_notification_sent=True)
            task = self.repo.get_by_id(task_id)
        except Exception:
            logger.exception(
                "Failed to post merge notification comment",
                extra={"task_id": task_id, "issue_number": task.github_issue_number},
            )

        refreshed = self.repo.get_by_id(task_id)
        if refreshed is None:
            return

        try:
            issue = await self.github_client.get_issue(
                refreshed.github_repository,
                refreshed.github_issue_number,
            )
            if issue.get("state") != "closed":
                await self.github_client.close_issue(
                    refreshed.github_repository,
                    refreshed.github_issue_number,
                )
        except Exception:
            logger.exception(
                "Failed to close originating issue after merge",
                extra={"task_id": task_id, "issue_number": refreshed.github_issue_number},
            )

    def _build_merge_comment(self, task: RemediationTask) -> str:
        lines = [
            "Remediation completed.",
            f"Pull request: {task.pr_url}",
            "Status: merged",
        ]
        if task.devin_session_url:
            lines.append(f"Devin session: {task.devin_session_url}")
        if task.acu_used is not None:
            lines.append(f"ACU consumed: {task.acu_used}")
        return "\n".join(lines)

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
        task = self.repo.update_task(task, status=TaskStatus.RECEIVED)
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
