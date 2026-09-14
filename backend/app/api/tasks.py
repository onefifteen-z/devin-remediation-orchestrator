from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.models.task import TaskStatus, TriggerSource
from app.repositories.tasks import TASK_SORT_FIELDS, TaskListQuery, TaskRepository
from app.schemas.task import TaskListResponse, TaskRefreshResponse, TaskResponse
from app.services.orchestration import RemediationOrchestrator

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    limit: int = Query(default=25, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    include_smoke_tests: bool = Query(
        default=False,
        description="Include smoke-test tasks (dummy label / task_kind=smoke_test).",
    ),
    status: TaskStatus | None = Query(default=None),
    trigger_source: TriggerSource | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskListResponse:
    if sort_by not in TASK_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sort_by. Allowed: {', '.join(sorted(TASK_SORT_FIELDS))}",
        )

    repo = TaskRepository(db)
    items, total = repo.list_tasks(
        TaskListQuery(
            limit=limit,
            offset=offset,
            include_smoke_tests=include_smoke_tests,
            status=status.value if status else None,
            trigger_source=trigger_source.value if trigger_source else None,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    )
    return TaskListResponse(
        items=[
            TaskResponse.from_orm_task(t, max_ci_repair_attempts=settings.max_ci_repair_attempts)
            for t in items
        ],
        total=total,
    )


@router.post("/refresh", response_model=TaskRefreshResponse)
async def refresh_tasks(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskRefreshResponse:
    orchestrator = RemediationOrchestrator(db, settings)
    try:
        result = await orchestrator.refresh_tasks_from_devin()
    finally:
        await orchestrator.devin_client.close()
    return TaskRefreshResponse(**result)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TaskResponse:
    repo = TaskRepository(db)
    task = repo.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_orm_task(task, max_ci_repair_attempts=settings.max_ci_repair_attempts)
