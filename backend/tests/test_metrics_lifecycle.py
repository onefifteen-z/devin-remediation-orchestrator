from datetime import UTC, datetime

from app.models.task import TaskStatus
from app.repositories.tasks import TaskRepository
from app.schemas.task import TaskCreate
from app.services.metrics import MetricsService


def _create_task(db_session, **fields):
    repo = TaskRepository(db_session)
    task = repo.create_task(
        TaskCreate(
            github_delivery_id=fields.pop("github_delivery_id", "metrics-001"),
            github_repository="owner/superset",
            github_issue_number=fields.pop("github_issue_number", 1),
            github_issue_url="https://github.com/owner/superset/issues/1",
            issue_title="Metrics test",
        )
    )
    if fields:
        task = repo.update_task(task, **fields)
    return task


def test_metrics_honest_when_no_merges(db_session):
    _create_task(
        db_session,
        github_delivery_id="metrics-running",
        github_issue_number=2,
        status=TaskStatus.RUNNING,
        devin_session_id="devin-1",
        acu_used=2.0,
        pr_url="https://github.com/owner/superset/pull/1",
    )
    metrics = MetricsService(db_session).compute()

    assert metrics.merge_rate == 0.0
    assert metrics.median_mttr_seconds is None
    assert metrics.tasks_with_prs == 1
    assert metrics.total_acu == 2.0
    assert metrics.average_acu_per_task == 2.0


def test_metrics_median_mttr_only_for_merged(db_session):
    repo = TaskRepository(db_session)
    task = _create_task(
        db_session,
        github_delivery_id="metrics-merged",
        github_issue_number=3,
    )
    started = datetime(2026, 1, 1, tzinfo=UTC)
    merged = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
    repo.update_status(
        task,
        TaskStatus.MERGED,
        started_at=started,
        merged_at=merged,
        completed_at=merged,
    )

    metrics = MetricsService(db_session).compute()
    assert metrics.median_mttr_seconds == 3600.0
    assert metrics.merge_rate > 0
