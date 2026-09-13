import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database import get_db
from app.schemas.remediation import RemediationCreateRequest, RemediationResponse
from app.services.devin import DevinAPIError, DevinAuthError
from app.services.orchestration import RemediationOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/remediations", tags=["remediations"])


@router.post("", response_model=RemediationResponse)
async def create_remediation(
    request: RemediationCreateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RemediationResponse:
    orchestrator = RemediationOrchestrator(db, settings)
    try:
        return await orchestrator.create_remediation(request)
    except DevinAuthError as exc:
        raise _map_devin_error(exc) from exc
    except DevinAPIError as exc:
        raise _map_devin_error(exc) from exc
    finally:
        await orchestrator.devin_client.close()


def _map_devin_error(exc: DevinAPIError) -> Exception:
    from fastapi import HTTPException

    safe_detail = str(exc)
    if exc.status_code is not None and exc.status_code >= 500:
        status_code = 503
    elif isinstance(exc, DevinAuthError):
        status_code = 502
    else:
        status_code = 502
    logger.error("Devin API error", extra={"status_code": exc.status_code})
    return HTTPException(status_code=status_code, detail=safe_detail)
