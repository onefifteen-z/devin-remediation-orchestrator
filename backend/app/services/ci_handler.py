import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.task import RemediationTask, TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.ci import (
    FAILURE_LIKE_CONCLUSIONS,
    IGNORED_CONCLUSIONS,
    CiCheckRunEvent,
    FailureType,
)
from app.services.failure_classifier import ClassificationResult, classify
from app.services.github_events import find_task_for_check_run
from app.services.session_lifecycle import is_valid_status_transition

logger = logging.getLogger(__name__)


@dataclass
class CiHandleResult:
    outcome: str
    task_id: int | None = None
    repair_message: str | None = None


def build_ci_repair_message(event: CiCheckRunEvent) -> str:
    check_name = event.check_name or "Unknown check"
    conclusion = event.conclusion or "unknown"
    summary = event.output_summary or event.output_title or "No details provided."

    return (
        "The existing pull request has a CI failure.\n\n"
        f"Check:\n{check_name}\n\n"
        f"Result:\n{conclusion}\n\n"
        f"Details:\n{summary}\n\n"
        "Please inspect the failing CI check and determine whether the failure "
        "is caused by your changes. If it is, diagnose the root cause, implement "
        "the appropriate correction, run the relevant tests, and update the "
        "existing pull request.\n\n"
        "Do not disable, weaken, or bypass valid tests.\n\n"
        "If the failure is unrelated to your changes or cannot be safely fixed, "
        "report the blocker instead of guessing."
    )


class CiFailureHandler:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repo = TaskRepository(db)

    def handle(self, event: CiCheckRunEvent) -> CiHandleResult:
        if event.status != "completed":
            logger.info(
                "ci_failure_ignored",
                extra={
                    "event": "check_run",
                    "delivery_id": event.delivery_id,
                    "repository": event.repository,
                    "check_run_id": event.check_run_id,
                    "check_name": event.check_name,
                    "reason": "non_terminal_status",
                    "status": event.status,
                },
            )
            return CiHandleResult(outcome="ignored")

        conclusion = (event.conclusion or "").lower()

        if conclusion in IGNORED_CONCLUSIONS or conclusion == "success":
            return self._handle_success_or_ignored(event, conclusion)

        if conclusion not in FAILURE_LIKE_CONCLUSIONS:
            logger.info(
                "ci_failure_ignored",
                extra={
                    "event": "check_run",
                    "delivery_id": event.delivery_id,
                    "repository": event.repository,
                    "check_run_id": event.check_run_id,
                    "conclusion": conclusion,
                    "reason": "non_failure_conclusion",
                },
            )
            return CiHandleResult(outcome="ignored")

        return self._handle_failure(event)

    def _handle_success_or_ignored(
        self, event: CiCheckRunEvent, conclusion: str
    ) -> CiHandleResult:
        if conclusion != "success":
            return CiHandleResult(outcome="ignored")

        task = find_task_for_check_run(self.repo, event.repository, event.pr_numbers)
        if not task:
            return CiHandleResult(outcome="ignored")

        updates: dict = {"last_ci_check_run_id": event.check_run_id}
        processed = False

        if task.ci_failure_at and task.ci_repair_verified_at is None:
            updates["ci_repair_verified_at"] = datetime.now(UTC)
            processed = True
            logger.info(
                "ci_repair_verified",
                extra={
                    "event": "check_run",
                    "delivery_id": event.delivery_id,
                    "task_id": task.id,
                    "check_run_id": event.check_run_id,
                    "repository": event.repository,
                },
            )

        if task.ci_passed_at is None:
            updates["ci_passed_at"] = datetime.now(UTC)
            processed = True
            logger.info(
                "ci_passed",
                extra={
                    "event": "check_run",
                    "delivery_id": event.delivery_id,
                    "task_id": task.id,
                    "check_run_id": event.check_run_id,
                    "repository": event.repository,
                },
            )

        if processed:
            self.repo.update_task(task, **updates)
            return CiHandleResult(outcome="processed", task_id=task.id)

        return CiHandleResult(outcome="ignored")

    def _handle_failure(self, event: CiCheckRunEvent) -> CiHandleResult:
        task = find_task_for_check_run(self.repo, event.repository, event.pr_numbers)
        if not task:
            logger.info(
                "ci_failure_ignored",
                extra={
                    "event": "check_run",
                    "delivery_id": event.delivery_id,
                    "repository": event.repository,
                    "check_run_id": event.check_run_id,
                    "pr_numbers": event.pr_numbers,
                    "reason": "no_matching_task",
                },
            )
            return CiHandleResult(outcome="no_matching_task")

        if task.last_ci_check_run_id == event.check_run_id:
            return CiHandleResult(outcome="already_processed", task_id=task.id)

        if not self.repo.try_claim_check_run(task.id, event.check_run_id):
            return CiHandleResult(outcome="already_processed", task_id=task.id)

        task = self.repo.get_by_id(task.id)
        assert task is not None

        pr_number = event.pr_numbers[0] if event.pr_numbers else None
        classification = classify(event)

        logger.info(
            "ci_failure_detected",
            extra={
                "event": "check_run",
                "delivery_id": event.delivery_id,
                "repository": event.repository,
                "pr_number": pr_number,
                "check_run_id": event.check_run_id,
                "check_name": event.check_name,
                "conclusion": event.conclusion,
                "task_id": task.id,
                "devin_session_id": task.devin_session_id,
            },
        )

        logger.info(
            "ci_failure_classified",
            extra={
                "event": "check_run",
                "delivery_id": event.delivery_id,
                "task_id": task.id,
                "check_run_id": event.check_run_id,
                "failure_type": classification.failure_type.value,
                "reason": classification.reason,
            },
        )

        self._persist_ci_metadata(task, event, classification)
        task = self.repo.get_by_id(task.id)
        assert task is not None

        return self._apply_policy(task, event, classification)

    def _persist_ci_metadata(
        self,
        task: RemediationTask,
        event: CiCheckRunEvent,
        classification: ClassificationResult,
    ) -> None:
        self.repo.update_task(
            task,
            failure_type=classification.failure_type.value,
            ci_classification_reason=classification.reason,
            ci_check_name=event.check_name,
            ci_check_url=event.check_url,
            ci_conclusion=event.conclusion,
            ci_failure_at=datetime.now(UTC),
        )

    def _apply_policy(
        self,
        task: RemediationTask,
        event: CiCheckRunEvent,
        classification: ClassificationResult,
    ) -> CiHandleResult:
        if classification.failure_type == FailureType.CODE_FAILURE:
            return self._apply_code_failure_policy(task, event, classification)

        return self._apply_non_code_failure_policy(task, event, classification)

    def _apply_code_failure_policy(
        self,
        task: RemediationTask,
        event: CiCheckRunEvent,
        classification: ClassificationResult,
    ) -> CiHandleResult:
        if task.ci_repair_attempts >= self.settings.max_ci_repair_attempts:
            self._escalate(
                task,
                f"CI repair attempts exceeded ({task.ci_repair_attempts}/"
                f"{self.settings.max_ci_repair_attempts})",
            )
            return CiHandleResult(outcome="processed", task_id=task.id)

        if not task.devin_session_id:
            logger.info(
                "ci_repair_escalated",
                extra={
                    "event": "check_run",
                    "task_id": task.id,
                    "check_run_id": event.check_run_id,
                    "reason": "no_devin_session_id",
                },
            )
            return CiHandleResult(outcome="processed", task_id=task.id)

        if not self.settings.devin_live_enabled:
            logger.info(
                "ci_repair_skipped",
                extra={
                    "event": "check_run",
                    "task_id": task.id,
                    "check_run_id": event.check_run_id,
                    "reason": "devin_live_disabled",
                },
            )
            return CiHandleResult(outcome="processed", task_id=task.id)

        claimed = self.repo.claim_ci_repair_attempt(
            task.id,
            event.check_run_id,
            self.settings.max_ci_repair_attempts,
        )
        if not claimed:
            self._escalate(
                task,
                f"CI repair attempts exceeded ({task.ci_repair_attempts}/"
                f"{self.settings.max_ci_repair_attempts})",
            )
            return CiHandleResult(outcome="processed", task_id=task.id)

        message = build_ci_repair_message(event)
        logger.info(
            "ci_repair_dispatched",
            extra={
                "event": "check_run",
                "task_id": task.id,
                "devin_session_id": task.devin_session_id,
                "check_run_id": event.check_run_id,
                "repair_attempt": claimed.ci_repair_attempts,
                "failure_type": classification.failure_type.value,
            },
        )
        return CiHandleResult(
            outcome="processed",
            task_id=task.id,
            repair_message=message,
        )

    def _apply_non_code_failure_policy(
        self,
        task: RemediationTask,
        event: CiCheckRunEvent,
        classification: ClassificationResult,
    ) -> CiHandleResult:
        new_count = task.ci_non_code_failure_count + 1
        self.repo.update_task(task, ci_non_code_failure_count=new_count)

        if new_count >= self.settings.max_ci_non_code_failures:
            self._escalate(
                task,
                f"Repeated non-code CI failures ({classification.failure_type.value}): "
                f"{new_count} occurrences",
            )
            logger.info(
                "ci_repair_escalated",
                extra={
                    "event": "check_run",
                    "task_id": task.id,
                    "check_run_id": event.check_run_id,
                    "failure_type": classification.failure_type.value,
                    "ci_non_code_failure_count": new_count,
                },
            )

        return CiHandleResult(outcome="processed", task_id=task.id)

    def _escalate(self, task: RemediationTask, reason: str) -> None:
        if not is_valid_status_transition(task.status, TaskStatus.ESCALATED):
            self.repo.update_task(task, escalation_reason=reason)
            return

        self.repo.update_status(
            task,
            TaskStatus.ESCALATED,
            escalation_reason=reason,
            completed_at=datetime.now(UTC),
        )
