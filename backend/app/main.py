from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.scheduler import scheduler
from app.services.budget import check_budget_thresholds
from app.services.ingestion import recover_stale_runs, run_ingestion
from app.services.notification import retry_failed_deliveries
from app.services.recommendation import run_recommendations


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup: clean up any stale 'running' ingestion runs from a previous crash
    async with AsyncSessionLocal() as session:
        await recover_stale_runs(session)

    # Initialize Redis client and store on app.state
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    # Register the 4-hour ingestion job
    scheduler.add_job(
        run_ingestion,
        "interval",
        hours=4,
        id="ingestion_scheduled",
        replace_existing=True,
        kwargs={"triggered_by": "scheduler"},
    )

    # Register daily recommendation job at 02:00 UTC (after Azure billing data lands)
    redis_client = app.state.redis

    async def _scheduled_recommendations():
        await run_recommendations(redis_client=redis_client)

    scheduler.add_job(
        _scheduled_recommendations,
        CronTrigger(hour=2, minute=0, timezone="UTC"),
        id="recommendation_daily",
        replace_existing=True,
    )

    # Register budget threshold check job — every 4 hours, 60 min after ingestion
    # Offset: ingestion runs at T+0h, anomaly at T+0h+30min, budget check at T+1h
    scheduler.add_job(
        check_budget_thresholds,
        "interval",
        hours=4,
        minutes=0,
        start_date="2026-01-01 01:00:00",  # 1-hour offset from ingestion start
        id="budget_threshold_check",
        replace_existing=True,
    )

    # Register webhook retry job — every 15 minutes
    scheduler.add_job(
        retry_failed_deliveries,
        "interval",
        minutes=15,
        id="webhook_retry",
        replace_existing=True,
    )

    scheduler.start()

    yield  # Application runs here

    # On shutdown: close Redis, stop scheduler
    await app.state.redis.aclose()
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="CloudCost API",
    version="1.0.0",
    docs_url="/api/docs",  # API-03: OpenAPI at /api/docs (NOT via router prefix)
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,  # Required for HttpOnly refresh token cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
