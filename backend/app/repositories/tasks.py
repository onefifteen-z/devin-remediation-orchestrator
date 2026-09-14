import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import asc, desc, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import ACTIVE_STATUSES, POLLABLE_STATUSES, RemediationTask, TaskStatus
from app.schemas.task import TaskCreate
from app.services.task_classification import smoke_test_sql_condition

TASK_SORT_FIELDS = {
    "created_at": RemediationTask.created_at,
    "merged_at": RemediationTask.merged_at,
    "status": RemediationTask.status,
    "repository": RemediationTask.github_repository,
    "issue_number": RemediationTask.github_issue_number,
    "issue_title": RemediationTask.issue_title,
    "trigger_source": RemediationTask.trigger_source,
}


@dataclass(frozen=True)
class TaskListQuery:
    limit: int = 25
    offset: int = 0
    include_smoke_tests: bool = False
    status: str | None = None
    trigger_source: str | None = None
    search: str | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"


class DuplicateDeliveryError(Exception):
    def __init__(self, existing_task: RemediationTask):
        self.existing_task = existing_task
        super().__init__(f"Duplicate delivery: {existing_task.github_delivery_id}")


class IssueAlreadyTrackedError(Exception):
    def __init__(self, existing_task: RemediationTask):
        self.existing_task = existing_task
        super().__init__(
            f"Issue already tracked: {existing_task.github_repository}"
            f"#{existing_task.github_issue_number}"
        )


class TaskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, data: TaskCreate) -> RemediationTask:
        existing_issue = self.get_by_issue(data.github_repository, data.github_issue_number)
        if existing_issue:
            raise IssueAlreadyTrackedError(existing_issue)

        existing_delivery = self.get_by_delivery_id(data.github_delivery_id)
        if existing_delivery:
            raise DuplicateDeliveryError(existing_delivery)

        task = RemediationTask(
            github_delivery_id=data.github_delivery_id,
            github_repository=data.github_repository,
            github_issue_number=data.github_issue_number,
            github_issue_url=data.github_issue_url,
            issue_title=data.issue_title,
            issue_type=data.issue_type,
            issue_labels=json.dumps(data.issue_labels) if data.issue_labels else None,
            task_kind=data.task_kind,
            trigger_source=data.trigger_source,
            max_retries=data.max_retries,
            status=TaskStatus.RECEIVED,
        )
        self.db.add(task)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing_issue = self.get_by_issue(data.github_repository, data.github_issue_number)
            if existing_issue:
                raise IssueAlreadyTrackedError(existing_issue) from None
            existing_delivery = self.get_by_delivery_id(data.github_delivery_id)
            if existing_delivery:
                raise DuplicateDeliveryError(existing_delivery) from None
            raise
        self.db.refresh(task)
        return task

    def get_by_id(self, task_id: int) -> RemediationTask | None:
        return self.db.get(RemediationTask, task_id)

    def get_by_delivery_id(self, delivery_id: str) -> RemediationTask | None:
        stmt = select(RemediationTask).where(
            RemediationTask.github_delivery_id == delivery_id
        )
        return self.db.scalars(stmt).first()

    def get_by_issue(self, repository: str, issue_number: int) -> RemediationTask | None:
        stmt = select(RemediationTask).where(
            RemediationTask.github_repository == repository,
            RemediationTask.github_issue_number == issue_number,
        )
        return self.db.scalars(stmt).first()

    def get_by_pr_url(self, pr_url: str) -> RemediationTask | None:
        stmt = select(RemediationTask).where(RemediationTask.pr_url == pr_url)
        return self.db.scalars(stmt).first()

    def get_by_repository_and_pr_number(
        self, repository: str, pr_number: int
    ) -> RemediationTask | None:
        suffix = f"/pull/{pr_number}"
        stmt = select(RemediationTask).where(
            RemediationTask.github_repository == repository,
            RemediationTask.pr_url.isnot(None),
            RemediationTask.pr_url.endswith(suffix),
        )
        return self.db.scalars(stmt).first()

    def _apply_task_list_filters(self, query, params: TaskListQuery):
        if not params.include_smoke_tests:
            query = query.where(~smoke_test_sql_condition())
        if params.status:
            query = query.where(RemediationTask.status == TaskStatus(params.status))
        if params.trigger_source:
            query = query.where(RemediationTask.trigger_source == params.trigger_source)
        if params.search:
            term = params.search.strip()
            if term.isdigit():
                query = query.where(
                    or_(
                        RemediationTask.github_issue_number == int(term),
                        RemediationTask.github_repository.ilike(f"%{term}%"),
                        RemediationTask.issue_title.ilike(f"%{term}%"),
                    )
                )
            else:
                query = query.where(
                    or_(
                        RemediationTask.github_repository.ilike(f"%{term}%"),
                        RemediationTask.issue_title.ilike(f"%{term}%"),
                    )
                )
        return query

    def list_tasks(self, params: TaskListQuery | None = None) -> tuple[list[RemediationTask], int]:
        params = params or TaskListQuery()
        base = select(RemediationTask)
        filtered = self._apply_task_list_filters(base, params)
        total = self.db.scalar(select(func.count()).select_from(filtered.subquery())) or 0

        sort_column = TASK_SORT_FIELDS.get(params.sort_by, RemediationTask.created_at)
        order_fn = desc if params.sort_order == "desc" else asc
        stmt = (
            filtered.order_by(order_fn(sort_column))
            .limit(params.limit)
            .offset(params.offset)
        )
        items = list(self.db.scalars(stmt).all())
        return items, total

    def update_task(self, task: RemediationTask, **fields) -> RemediationTask:
        for key, value in fields.items():
            setattr(task, key, value)
        task.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(task)
        return task

    def update_status(self, task: RemediationTask, status: TaskStatus, **fields) -> RemediationTask:
        fields["status"] = status
        return self.update_task(task, **fields)

    def claim_task_if_received(self, task_id: int) -> RemediationTask | None:
        """Atomically claim a RECEIVED task for processing without changing status."""
        now = datetime.now(UTC)
        stmt = (
            update(RemediationTask)
            .where(
                RemediationTask.id == task_id,
                RemediationTask.status == TaskStatus.RECEIVED,
                RemediationTask.started_at.is_(None),
            )
            .values(
                started_at=now,
                updated_at=now,
            )
        )
        result = self.db.execute(stmt)
        self.db.commit()
        if result.rowcount != 1:
            return None
        return self.get_by_id(task_id)

    def count_active_sessions(self) -> int:
        stmt = (
            select(func.count())
            .select_from(RemediationTask)
            .where(RemediationTask.status.in_(ACTIVE_STATUSES))
        )
        return self.db.scalar(stmt) or 0

    def list_pollable_tasks(self) -> list[RemediationTask]:
        stmt = (
            select(RemediationTask)
            .where(
                RemediationTask.devin_session_id.isnot(None),
                RemediationTask.status.in_(POLLABLE_STATUSES),
            )
            .order_by(RemediationTask.updated_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def claim_task_for_polling(self, task_id: int) -> RemediationTask | None:
        """Atomically claim a pollable task for session sync."""
        now = datetime.now(UTC)
        stmt = (
            update(RemediationTask)
            .where(
                RemediationTask.id == task_id,
                RemediationTask.devin_session_id.isnot(None),
                RemediationTask.status.in_(POLLABLE_STATUSES),
            )
            .values(updated_at=now)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        if result.rowcount != 1:
            return None
        return self.get_by_id(task_id)

    def list_all(self) -> list[RemediationTask]:
        stmt = select(RemediationTask).order_by(RemediationTask.created_at.desc())
        return list(self.db.scalars(stmt).all())

    def try_claim_check_run(self, task_id: int, check_run_id: int) -> bool:
        """Atomically claim a check_run for processing. Returns False if already processed."""
        now = datetime.now(UTC)
        stmt = (
            update(RemediationTask)
            .where(
                RemediationTask.id == task_id,
                or_(
                    RemediationTask.last_ci_check_run_id.is_(None),
                    RemediationTask.last_ci_check_run_id != check_run_id,
                ),
            )
            .values(last_ci_check_run_id=check_run_id, updated_at=now)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount == 1

    def claim_ci_repair_attempt(
        self, task_id: int, check_run_id: int, max_attempts: int
    ) -> RemediationTask | None:
        """Atomically increment CI repair attempts if under limit."""
        now = datetime.now(UTC)
        stmt = (
            update(RemediationTask)
            .where(
                RemediationTask.id == task_id,
                RemediationTask.ci_repair_attempts < max_attempts,
                RemediationTask.last_ci_check_run_id == check_run_id,
            )
            .values(
                ci_repair_attempts=RemediationTask.ci_repair_attempts + 1,
                ci_repair_message_sent_at=now,
                updated_at=now,
            )
        )
        result = self.db.execute(stmt)
        self.db.commit()
        if result.rowcount != 1:
            return None
        return self.get_by_id(task_id)
