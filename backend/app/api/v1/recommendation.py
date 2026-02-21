"""Recommendation FastAPI router.

Endpoints:
  GET  /recommendations/         - List latest recommendations (filterable)
  GET  /recommendations/summary  - Summary stats + daily limit status
  POST /recommendations/run      - Admin: trigger generation (fire-and-forget)
"""
import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.ingestion import require_admin
from app.core.dependencies import get_db
from app.core.redis import get_redis
from app.models.user import User
from app.schemas.recommendation import RecommendationOut, RecommendationSummary
from app.services.recommendation import (
    get_latest_recommendations,
    get_recommendation_summary,
    run_recommendations,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=list[RecommendationOut])
async def list_recommendations(
    category: str | None = Query(None, description="Filter: right-sizing, idle, reserved, storage"),
    min_savings: float | None = Query(None, description="Minimum estimated monthly savings (USD)"),
    min_confidence: int | None = Query(None, description="Minimum confidence score (0-100)"),
    session: AsyncSession = Depends(get_db),
):
    """Return the latest set of recommendations with optional filters."""
    return await get_latest_recommendations(
        session, category=category, min_savings=min_savings, min_confidence=min_confidence
    )


@router.get("/summary", response_model=RecommendationSummary)
async def recommendation_summary(
    session: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis),
):
    """Return summary stats: total count, potential savings, per-category counts, daily limit status."""
    return await get_recommendation_summary(session, redis_client)


@router.post("/run", status_code=202)
async def trigger_recommendations(
    redis_client: aioredis.Redis = Depends(get_redis),
    _admin: User = Depends(require_admin),
):
    """Admin: trigger recommendation generation immediately (fire-and-forget).

    Returns 202 Accepted. Generation runs in background. Refresh the page
    after a few seconds to see new recommendations.
    """
    asyncio.create_task(run_recommendations(redis_client=redis_client))
    logger.info("Recommendation generation triggered manually by admin")
    return {"message": "Recommendation generation started"}
