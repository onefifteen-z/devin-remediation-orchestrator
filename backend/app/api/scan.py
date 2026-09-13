import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.webhooks import _process_task_background
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.scan import ScanResult
from app.services.orchestration import RemediationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scan", tags=["scan"])


@router.post("/github", response_model=ScanResult)
async def scan_github_issues(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ScanResult:
    if not settings.github_token:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN is not configured")

    repositories = settings.github_scan_repositories_list()
    if not repositories:
        raise HTTPException(
            status_code=400,
            detail="GITHUB_SCAN_REPOSITORIES is not configured",
        )

    orchestrator = RemediationOrchestrator(db, settings)
    try:
        result = await orchestrator.scan_labeled_issues()
    finally:
        await orchestrator.github_client.close()

    for task_id in result.created_task_ids:
        background_tasks.add_task(_process_task_background, task_id)

    logger.info(
        "GitHub issue scan completed",
        extra={
            "scanned": result.scanned,
            "created": result.created,
            "skipped": result.skipped,
        },
    )

    return result
