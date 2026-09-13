from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.task import ACTIVE_STATUSES, POLLABLE_STATUSES, RemediationTask, TaskStatus
from app.schemas.task import TaskCreate


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

    def list_tasks(self, limit: int = 100, offset: int = 0) -> tuple[list[RemediationTask], int]:
        total = self.db.scalar(select(func.count()).select_from(RemediationTask)) or 0
        stmt = (
            select(RemediationTask)
            .order_by(RemediationTask.created_at.desc())
            .limit(limit)
            .offset(offset)
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
