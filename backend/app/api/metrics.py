from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.metrics import MetricsResponse
from app.services.metrics import MetricsService

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
async def get_metrics(db: Session = Depends(get_db)) -> MetricsResponse:
    return await MetricsService(db).compute_with_analytics()
