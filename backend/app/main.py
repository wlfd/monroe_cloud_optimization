from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from app.core.scheduler import scheduler
from app.services.ingestion import run_ingestion, recover_stale_runs
from app.core.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: clean up any stale 'running' ingestion runs from a previous crash
    async with AsyncSessionLocal() as session:
        await recover_stale_runs(session)

    # Register the 4-hour ingestion job and start the scheduler
    scheduler.add_job(
        run_ingestion,
        "interval",
        hours=4,
        id="ingestion_scheduled",
        replace_existing=True,
        kwargs={"triggered_by": "scheduler"},
    )
    scheduler.start()

    yield  # Application runs here

    # On shutdown: stop the scheduler cleanly
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="CloudCost API",
    version="1.0.0",
    docs_url="/api/docs",     # API-03: OpenAPI at /api/docs (NOT via router prefix)
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,   # Required for HttpOnly refresh token cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
