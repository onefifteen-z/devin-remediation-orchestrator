import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.webhooks import _process_task_background
from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.scan import ScanResult
from app.services.orchestration import RemediationOrchestrator
from app.utils.security import verify_bearer_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduled", tags=["scheduled"])


def _intake_token_required(settings: Settings) -> bool:
    return bool(settings.orchestrator_public_url) or settings.devin_scheduled_enabled


def _validate_intake_token(
    settings: Settings,
    authorization: str | None,
) -> None:
    if not _intake_token_required(settings):
        return
    if not settings.scheduled_intake_token:
        raise HTTPException(status_code=401, detail="Scheduled intake token required")
    if not verify_bearer_token(authorization, settings.scheduled_intake_token):
        raise HTTPException(status_code=401, detail="Invalid scheduled intake token")


@router.post("/intake", response_model=ScanResult)
async def scheduled_intake(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    authorization: str | None = Header(default=None),
) -> ScanResult:
    _validate_intake_token(settings, authorization)

    if not settings.github_token:
        raise HTTPException(status_code=503, detail="GITHUB_TOKEN is not configured")

    repositories = settings.github_scan_repositories_list()
    if not repositories:
        raise HTTPException(
            status_code=400,
            detail="GITHUB_SCAN_REPOSITORIES is not configured",
        )

    run_id = uuid.uuid4().hex[:12]
    orchestrator = RemediationOrchestrator(db, settings)
    try:
        result = await orchestrator.scan_labeled_issues(
            source="scheduled",
            delivery_prefix="scheduled",
            run_id=run_id,
            label=settings.scheduled_label,
        )
    finally:
        await orchestrator.github_client.close()

    for task_id in result.created_task_ids:
        background_tasks.add_task(_process_task_background, task_id)

    logger.info(
        "Scheduled intake completed",
        extra={
            "schedule_run_id": run_id,
            "run_time": datetime.now(UTC).isoformat(),
            "scanned": result.scanned,
            "created": result.created,
            "skipped": result.skipped,
            "created_task_ids": result.created_task_ids,
            "skipped_issues": result.skipped_issues,
        },
    )

    return result
