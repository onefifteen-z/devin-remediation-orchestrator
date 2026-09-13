import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db, get_session_factory
from app.repositories.tasks import DuplicateDeliveryError, IssueAlreadyTrackedError
from app.schemas.task import RemediationEvent, TaskResponse
from app.services.orchestration import RemediationOrchestrator
from app.utils.security import verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

REMEDIATE_LABEL = "devin-remediate"


def _extract_issue_type(labels: list[dict]) -> str:
    for label in labels:
        name = label.get("name", "")
        if name != REMEDIATE_LABEL:
            return name
    return "unknown"


def _is_remediation_trigger(event: str, payload: dict) -> bool:
    if event != "issues":
        return False
    if payload.get("action") != "labeled":
        return False
    label = payload.get("label", {})
    return label.get("name") == REMEDIATE_LABEL


def _normalize_event(delivery_id: str, payload: dict) -> RemediationEvent:
    issue = payload["issue"]
    repository = payload["repository"]["full_name"]
    labels = issue.get("labels", [])
    return RemediationEvent(
        github_delivery_id=delivery_id,
        github_repository=repository,
        github_issue_number=issue["number"],
        github_issue_url=issue["html_url"],
        issue_title=issue.get("title", ""),
        issue_type=_extract_issue_type(labels),
    )


async def _process_task_background(task_id: int) -> None:
    db = get_session_factory()()
    try:
        settings = get_settings()
        orchestrator = RemediationOrchestrator(db, settings)
        await orchestrator.process_task(task_id)
    except Exception:
        logger.exception("Background task processing failed", extra={"task_id": task_id})
    finally:
        db.close()


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict:
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    if not _is_remediation_trigger(x_github_event or "", payload):
        return {"status": "ignored", "reason": "not a remediation trigger"}

    event = _normalize_event(x_github_delivery, payload)
    orchestrator = RemediationOrchestrator(db, settings)

    try:
        task, outcome = orchestrator.handle_webhook_event(event)
    except DuplicateDeliveryError as exc:
        return {
            "status": "duplicate",
            "task": TaskResponse.from_orm_task(exc.existing_task).model_dump(),
        }
    except IssueAlreadyTrackedError as exc:
        return {
            "status": "duplicate",
            "task": TaskResponse.from_orm_task(exc.existing_task).model_dump(),
        }

    if outcome == "skipped":
        return {
            "status": "duplicate",
            "task": TaskResponse.from_orm_task(task).model_dump(),
        }

    logger.info(
        "Remediation task created",
        extra={
            "task_id": task.id,
            "github_delivery_id": event.github_delivery_id,
            "repository": event.github_repository,
            "issue_number": event.github_issue_number,
        },
    )

    background_tasks.add_task(_process_task_background, task.id)

    return {
        "status": "accepted",
        "task": TaskResponse.from_orm_task(task).model_dump(),
    }
