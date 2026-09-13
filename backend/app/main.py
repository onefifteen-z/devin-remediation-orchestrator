import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import health, metrics, remediations, scan, tasks, webhooks
from app.config import get_settings
from app.database import get_session_factory, init_db
from app.services.devin import DevinClient
from app.workers.poller import SessionPoller

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    logger.info("Database initialized")

    devin_client = DevinClient(settings)
    poller = SessionPoller(settings, get_session_factory(), devin_client)
    poller_task = poller.start_background()

    yield

    await poller.stop()
    await devin_client.close()
    if not poller_task.done():
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Devin Remediation Orchestrator",
    description="Event-driven autonomous remediation platform powered by Devin",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(tasks.router)
app.include_router(metrics.router)
app.include_router(remediations.router)
app.include_router(scan.router)
app.include_router(webhooks.router)


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, _exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
