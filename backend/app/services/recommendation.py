"""Recommendation generation service.

Implements the daily LLM-powered cost optimization pipeline:
- Qualify resources (monthly spend >= LLM_MIN_MONTHLY_SPEND_THRESHOLD)
- Check Redis cache per resource (24hr TTL) — AI-03
- Check/increment daily call counter (Redis INCR+EXPIREAT) — AI-04
- Call Anthropic Claude Sonnet 4.6 via tool_choice forced structured output
- Fallback to Azure OpenAI on non-transient failures after 3 retries
- Insert new Recommendation rows (generated_date = today)

Query pattern: get_latest_recommendations always queries WHERE generated_date
= MAX(generated_date) — no DELETE, logical daily replace.
"""
import json
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import anthropic
import redis.asyncio as aioredis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.billing import BillingRecord
from app.models.recommendation import Recommendation

logger = logging.getLogger(__name__)

# Forced-output tool definition (AI-02)
RECOMMENDATION_TOOL = {
    "name": "record_recommendation",
    "description": (
        "Record a cloud cost optimization recommendation for the given Azure resource. "
        "Always call this tool with your analysis results."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["right-sizing", "idle", "reserved", "storage"],
                "description": "The optimization category for this resource",
            },
            "explanation": {
                "type": "string",
                "description": "Plain-language explanation of the recommendation (2-4 sentences)",
            },
            "estimated_monthly_savings": {
                "type": "number",
                "description": "Estimated monthly savings in USD if recommendation is applied",
            },
            "confidence_score": {
                "type": "integer",
                "description": "Confidence in this recommendation, 0–100",
                "minimum": 0,
                "maximum": 100,
            },
        },
        "required": [
            "category",
            "explanation",
            "estimated_monthly_savings",
            "confidence_score",
        ],
    },
}


# ---------------------------------------------------------------------------
# Cache and counter helpers
# ---------------------------------------------------------------------------

def _make_cache_key(subscription_id: str, resource_group: str, resource_name: str) -> str:
    today = date.today().isoformat()
    return f"rec:cache:{subscription_id}:{resource_group}:{resource_name}:{today}"


def _daily_counter_key() -> str:
    return f"rec:daily_calls:{date.today().isoformat()}"


def _midnight_expiry() -> int:
    now = datetime.now(UTC)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())


async def _check_and_increment_counter(redis_client: aioredis.Redis, limit: int) -> bool:
    """Atomically increment daily call counter.

    Returns True if call is allowed (under limit), False if limit exceeded.
    Sets EXPIREAT to midnight UTC on first call of the day.
    Only called on cache miss — cache hits do not count against the limit.
    """
    key = _daily_counter_key()
    current = await redis_client.incr(key)
    if current == 1:
        await redis_client.expireat(key, _midnight_expiry())
    return current <= limit


async def _get_calls_used_today(redis_client: aioredis.Redis) -> int:
    key = _daily_counter_key()
    val = await redis_client.get(key)
    return int(val) if val else 0


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(resource: dict) -> str:
    cost_lines = "\n".join(
        f"  {row['date']}: ${row['cost']:.2f}" for row in resource["cost_history"]
    )
    return (
        f"Analyze this Azure resource for cost optimization:\n"
        f"Resource name: {resource['resource_name']}\n"
        f"Resource type: {resource['service_name']}\n"
        f"Resource group: {resource['resource_group']}\n"
        f"Subscription: {resource['subscription_id']}\n"
        f"Service category: {resource['meter_category']}\n"
        f"Last 30 days of billed cost:\n{cost_lines}\n\n"
        f"Provide a specific, actionable cost optimization recommendation."
    )


# ---------------------------------------------------------------------------
# Anthropic LLM call with retry
# ---------------------------------------------------------------------------

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)
    ),
)
async def _call_anthropic(client: anthropic.AsyncAnthropic, resource: dict) -> dict:
    """Call Anthropic Claude with tool_choice forcing structured JSON output."""
    response = await client.messages.create(
        model=get_settings().ANTHROPIC_MODEL,
        max_tokens=512,
        tools=[RECOMMENDATION_TOOL],
        tool_choice={"type": "tool", "name": "record_recommendation"},
        messages=[{"role": "user", "content": _build_prompt(resource)}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_recommendation":
            return block.input
    raise ValueError("No tool_use block in response")


# ---------------------------------------------------------------------------
# Azure OpenAI fallback
# ---------------------------------------------------------------------------

async def _call_azure_openai(resource: dict) -> dict | None:
    """Attempt Azure OpenAI fallback. Returns structured dict or None on failure.

    Only invoked when Anthropic fails all retries. If AZURE_OPENAI_ENDPOINT or
    AZURE_OPENAI_API_KEY are unset, logs a warning and returns None (graceful no-op).
    """
    settings = get_settings()
    if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
        logger.warning(
            "_call_azure_openai: fallback unconfigured (AZURE_OPENAI_ENDPOINT/KEY not set), skipping"
        )
        return None
    try:
        from openai import AsyncAzureOpenAI  # optional dependency

        az_client = AsyncAzureOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version="2024-02-01",
        )
        response = await az_client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cloud cost optimization expert. "
                        "Always respond with a JSON object containing exactly these fields: "
                        "category (one of: right-sizing, idle, reserved, storage), "
                        "explanation (string, 2-4 sentences), "
                        "estimated_monthly_savings (number, USD), "
                        "confidence_score (integer, 0-100)."
                    ),
                },
                {"role": "user", "content": _build_prompt(resource)},
            ],
        )
        return json.loads(response.choices[0].message.content)
    except Exception as exc:
        logger.error("_call_azure_openai: fallback also failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core get_or_generate with cache
# ---------------------------------------------------------------------------

async def _get_or_generate(
    redis_client: aioredis.Redis,
    anthropic_client: anthropic.AsyncAnthropic,
    resource: dict,
    daily_limit: int,
) -> dict | None:
    """Check Redis cache; on miss check limit and call LLM.

    Returns structured recommendation dict or None if:
    - Cache miss AND daily limit reached
    - Cache miss AND all LLM calls (primary + fallback) failed

    Cache hits never count against the daily limit.
    """
    cache_key = _make_cache_key(
        resource["subscription_id"], resource["resource_group"], resource["resource_name"]
    )

    # Cache hit: return immediately, do not count against limit
    cached = await redis_client.get(cache_key)
    if cached:
        logger.debug("Cache hit for resource: %s", resource["resource_name"])
        return json.loads(cached)

    # Cache miss: check daily limit before calling LLM
    allowed = await _check_and_increment_counter(redis_client, daily_limit)
    if not allowed:
        logger.info(
            "Daily LLM call limit (%d) reached, stopping generation", daily_limit
        )
        return None

    # Attempt Anthropic primary
    result = None
    try:
        result = await _call_anthropic(anthropic_client, resource)
    except Exception as exc:
        logger.warning("Anthropic call failed for %s: %s — trying fallback", resource["resource_name"], exc)
        result = await _call_azure_openai(resource)

    if result is None:
        return None

    # Cache the result for 24 hours
    await redis_client.set(cache_key, json.dumps(result), ex=86400)
    return result


# ---------------------------------------------------------------------------
# Main run_recommendations function
# ---------------------------------------------------------------------------

async def run_recommendations(redis_client: aioredis.Redis | None = None) -> None:
    """Daily recommendation generation job.

    Qualifies resources (monthly spend >= threshold), sorted by spend desc.
    Highest spenders processed first — when daily limit hit mid-run, best
    coverage of expensive resources is guaranteed.

    Uses generated_date for logical daily replace: new rows use today's date;
    GET /recommendations/ queries MAX(generated_date) so old rows remain
    visible until the new batch is complete (no DELETE flash).

    Called by: APScheduler CronTrigger (02:00 UTC) and POST /run admin endpoint.
    """
    settings = get_settings()

    async with AsyncSessionLocal() as session:
        await _run_recommendations_with_session(session, redis_client, settings)


async def _run_recommendations_with_session(session: AsyncSession, redis_client, settings) -> None:
    # If redis_client not provided (e.g., called from scheduler before lifespan),
    # this is a coding error — log and return
    if redis_client is None:
        logger.error("run_recommendations: redis_client is None — cannot generate recommendations")
        return

    if not settings.ANTHROPIC_API_KEY:
        logger.warning(
            "run_recommendations: ANTHROPIC_API_KEY not set — skipping generation"
        )
        return

    anthropic_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Qualify resources: resource_name + resource_group with monthly spend >= threshold
    # Use current month billing data, group by resource identity
    today = date.today()
    month_start = today.replace(day=1)

    qualify_stmt = (
        select(
            BillingRecord.resource_name,
            BillingRecord.resource_group,
            BillingRecord.subscription_id,
            BillingRecord.service_name,
            BillingRecord.meter_category,
            func.sum(BillingRecord.pre_tax_cost).label("monthly_cost"),
        )
        .where(
            BillingRecord.usage_date >= month_start,
            BillingRecord.usage_date <= today,
            BillingRecord.resource_name != "",
        )
        .group_by(
            BillingRecord.resource_name,
            BillingRecord.resource_group,
            BillingRecord.subscription_id,
            BillingRecord.service_name,
            BillingRecord.meter_category,
        )
        .having(func.sum(BillingRecord.pre_tax_cost) >= settings.LLM_MIN_MONTHLY_SPEND_THRESHOLD)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())  # highest spenders first
    )

    qualifying = (await session.execute(qualify_stmt)).all()

    if not qualifying:
        logger.info("run_recommendations: no qualifying resources found")
        return

    logger.info("run_recommendations: %d qualifying resources", len(qualifying))

    # Fetch last 30 days of billing history per resource (for prompt context)
    thirty_days_ago = today - timedelta(days=30)

    generated = 0
    limit_reached = False

    for resource_row in qualifying:
        # Build cost history for prompt
        history_stmt = (
            select(BillingRecord.usage_date, func.sum(BillingRecord.pre_tax_cost).label("cost"))
            .where(
                BillingRecord.resource_name == resource_row.resource_name,
                BillingRecord.resource_group == resource_row.resource_group,
                BillingRecord.usage_date >= thirty_days_ago,
            )
            .group_by(BillingRecord.usage_date)
            .order_by(BillingRecord.usage_date)
        )
        history_rows = (await session.execute(history_stmt)).all()

        resource = {
            "resource_name": resource_row.resource_name,
            "resource_group": resource_row.resource_group,
            "subscription_id": resource_row.subscription_id,
            "service_name": resource_row.service_name,
            "meter_category": resource_row.meter_category,
            "monthly_cost": float(resource_row.monthly_cost),
            "cost_history": [
                {"date": str(r.usage_date), "cost": float(r.cost)} for r in history_rows
            ],
        }

        llm_result = await _get_or_generate(
            redis_client, anthropic_client, resource, settings.LLM_DAILY_CALL_LIMIT
        )

        if llm_result is None:
            limit_reached = True
            break

        # Insert recommendation row (generated_date = today for logical daily replace)
        rec = Recommendation(
            generated_date=today,
            resource_name=resource_row.resource_name,
            resource_group=resource_row.resource_group,
            subscription_id=resource_row.subscription_id,
            service_name=resource_row.service_name,
            meter_category=resource_row.meter_category,
            category=llm_result["category"],
            explanation=llm_result["explanation"],
            estimated_monthly_savings=Decimal(str(llm_result["estimated_monthly_savings"])),
            confidence_score=int(llm_result["confidence_score"]),
            current_monthly_cost=Decimal(str(resource["monthly_cost"])),
        )
        session.add(rec)
        generated += 1

    # Commit all new rows at once (single transaction, not per-row)
    await session.commit()

    logger.info(
        "run_recommendations: generated=%d, limit_reached=%s", generated, limit_reached
    )


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

async def get_latest_recommendations(
    session: AsyncSession,
    *,
    category: str | None = None,
    min_savings: float | None = None,
    min_confidence: int | None = None,
) -> list:
    """Return recommendations for the most recent generated_date.

    Uses MAX(generated_date) subquery — no DELETE semantics, always returns
    a coherent set even during generation.
    """
    max_date_stmt = select(func.max(Recommendation.generated_date))
    latest_date = (await session.execute(max_date_stmt)).scalar()
    if latest_date is None:
        return []

    stmt = select(Recommendation).where(Recommendation.generated_date == latest_date)

    if category is not None:
        stmt = stmt.where(Recommendation.category == category)
    if min_savings is not None:
        stmt = stmt.where(Recommendation.estimated_monthly_savings >= min_savings)
    if min_confidence is not None:
        stmt = stmt.where(Recommendation.confidence_score >= min_confidence)

    stmt = stmt.order_by(Recommendation.estimated_monthly_savings.desc())
    return (await session.execute(stmt)).scalars().all()


async def get_recommendation_summary(session: AsyncSession, redis_client: aioredis.Redis) -> dict:
    """Compute summary stats for the recommendations page header."""
    recs = await get_latest_recommendations(session)

    total_count = len(recs)
    potential_monthly_savings = sum(float(r.estimated_monthly_savings) for r in recs)

    by_category: dict[str, int] = {"right-sizing": 0, "idle": 0, "reserved": 0, "storage": 0}
    for r in recs:
        if r.category in by_category:
            by_category[r.category] += 1

    settings = get_settings()
    calls_used_today = await _get_calls_used_today(redis_client)
    daily_limit = settings.LLM_DAILY_CALL_LIMIT
    daily_limit_reached = calls_used_today >= daily_limit

    return {
        "total_count": total_count,
        "potential_monthly_savings": round(potential_monthly_savings, 2),
        "by_category": by_category,
        "daily_limit_reached": daily_limit_reached,
        "calls_used_today": calls_used_today,
        "daily_call_limit": daily_limit,
    }
