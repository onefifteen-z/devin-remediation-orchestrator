import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db, get_session_factory
from app.repositories.tasks import TaskRepository
from app.repositories.webhook_deliveries import WebhookDeliveryAlreadyProcessedError
from app.schemas.github_events import (
    REMEDIATE_LABEL,
    normalize_issue_event,
    normalize_pull_request_event,
)
from app.schemas.ci import normalize_check_run_event
from app.schemas.task import RemediationEvent, TaskResponse
from app.services.ci_handler import CiFailureHandler
from app.services.devin import DevinClient
from app.services.orchestration import RemediationOrchestrator
from app.utils.security import verify_github_signature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _is_remediation_trigger(event: str, payload: dict) -> bool:
    if event != "issues":
        return False
    if payload.get("action") != "labeled":
        return False
    label = payload.get("label", {})
    return label.get("name") == REMEDIATE_LABEL


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


async def _post_merge_actions_background(task_id: int) -> None:
    db = get_session_factory()()
    try:
        settings = get_settings()
        orchestrator = RemediationOrchestrator(db, settings)
        await orchestrator.post_merge_github_actions(task_id)
    except Exception:
        logger.exception("Post-merge GitHub actions failed", extra={"task_id": task_id})
    finally:
        db.close()


async def _send_ci_repair_message_background(task_id: int, message: str) -> None:
    db = get_session_factory()()
    try:
        settings = get_settings()
        repo = TaskRepository(db)
        task = repo.get_by_id(task_id)
        if not task or not task.devin_session_id:
            logger.error(
                "CI repair message skipped: missing task or session",
                extra={"task_id": task_id},
            )
            return

        devin_client = DevinClient(settings)
        try:
            await devin_client.send_message(task.devin_session_id, message)
            logger.info(
                "CI repair message sent",
                extra={
                    "task_id": task_id,
                    "devin_session_id": task.devin_session_id,
                },
            )
        except Exception:
            logger.exception(
                "CI repair message failed",
                extra={
                    "task_id": task_id,
                    "devin_session_id": task.devin_session_id,
                },
            )
        finally:
            await devin_client.close()
    finally:
        db.close()


def _handle_issue_event(
    orchestrator: RemediationOrchestrator,
    delivery_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
) -> tuple[dict, int]:
    if not _is_remediation_trigger("issues", payload):
        orchestrator.webhook_repo.record(
            delivery_id,
            event_type="issues",
            action=payload.get("action"),
            repository=payload.get("repository", {}).get("full_name"),
            outcome="ignored",
        )
        return {"outcome": "ignored"}, 200

    event = RemediationEvent(**normalize_issue_event(delivery_id, payload))
    task, outcome = orchestrator.handle_webhook_event(event)

    if outcome == "skipped":
        orchestrator.webhook_repo.record(
            delivery_id,
            event_type="issues",
            action=event.action,
            repository=event.github_repository,
            task_id=task.id,
            outcome="duplicate",
        )
        return {"outcome": "duplicate", "task_id": task.id}, 200

    orchestrator.webhook_repo.record(
        delivery_id,
        event_type="issues",
        action=event.action,
        repository=event.github_repository,
        task_id=task.id,
        outcome="accepted",
    )

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
    return {"outcome": "accepted", "task_id": task.id}, 202


def _handle_pull_request_event(
    orchestrator: RemediationOrchestrator,
    delivery_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
) -> tuple[dict, int]:
    event = normalize_pull_request_event(delivery_id, payload)
    outcome, task_id = orchestrator.handle_pull_request_event(event)

    orchestrator.webhook_repo.record(
        delivery_id,
        event_type=event.event_type,
        action=event.action,
        repository=event.repository,
        task_id=task_id,
        outcome=outcome,
    )

    if outcome == "ignored":
        return {"outcome": "ignored"}, 200

    response: dict = {"outcome": outcome}
    if task_id is not None:
        response["task_id"] = task_id
    if outcome == "merged" and task_id is not None:
        background_tasks.add_task(_post_merge_actions_background, task_id)

    return response, 200


def _handle_check_run_event(
    db: Session,
    settings: Settings,
    delivery_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
) -> tuple[dict, int]:
    event = normalize_check_run_event(delivery_id, payload)
    handler = CiFailureHandler(db, settings)
    result = handler.handle(event)

    orchestrator = RemediationOrchestrator(db, settings)
    orchestrator.webhook_repo.record(
        delivery_id,
        event_type="check_run",
        action=event.action,
        repository=event.repository,
        task_id=result.task_id,
        outcome=result.outcome,
    )

    if result.repair_message and result.task_id is not None:
        background_tasks.add_task(
            _send_ci_repair_message_background,
            result.task_id,
            result.repair_message,
        )

    response: dict = {"outcome": result.outcome}
    if result.task_id is not None:
        response["task_id"] = result.task_id
    return response, 200


@router.post("/github")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_github_delivery: str | None = Header(default=None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> Response:
    body = await request.body()

    if not verify_github_signature(body, x_hub_signature_256, settings.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not x_github_delivery:
        raise HTTPException(status_code=400, detail="Missing X-GitHub-Delivery header")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    orchestrator = RemediationOrchestrator(db, settings)

    if orchestrator.webhook_repo.is_processed(x_github_delivery):
        return Response(
            content=json.dumps({"outcome": "duplicate"}),
            status_code=200,
            media_type="application/json",
        )

    event_type = x_github_event or ""

    try:
        if event_type == "issues":
            response_body, status_code = _handle_issue_event(
                orchestrator, x_github_delivery, payload, background_tasks
            )
        elif event_type == "pull_request":
            response_body, status_code = _handle_pull_request_event(
                orchestrator, x_github_delivery, payload, background_tasks
            )
        elif event_type == "check_run":
            response_body, status_code = _handle_check_run_event(
                db, settings, x_github_delivery, payload, background_tasks
            )
        else:
            orchestrator.webhook_repo.record(
                x_github_delivery,
                event_type=event_type,
                action=payload.get("action"),
                repository=payload.get("repository", {}).get("full_name"),
                outcome="ignored",
            )
            response_body, status_code = {"outcome": "ignored"}, 200
    except WebhookDeliveryAlreadyProcessedError:
        return Response(
            content=json.dumps({"outcome": "duplicate"}),
            status_code=200,
            media_type="application/json",
        )

    return Response(
        content=json.dumps(response_body),
        status_code=status_code,
        media_type="application/json",
    )
