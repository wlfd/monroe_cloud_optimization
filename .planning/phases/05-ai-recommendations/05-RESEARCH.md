# Phase 5: AI Recommendations - Research

**Researched:** 2026-02-21
**Domain:** LLM integration (Anthropic), Redis caching, APScheduler job scheduling, FastAPI service layer, React card UI
**Confidence:** HIGH (core stack verified against official docs and existing codebase patterns)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Recommendation layout:** Card-based list (expandable rows stacked vertically), matching reference design. Each card shows: resource name, category badge, risk/confidence badge, estimated savings/mo, confidence %, current → recommended comparison panel, cost trend data from billing (not CPU/memory), LLM explanation inline (always visible).
- **Summary stat row at top:** Potential Monthly Savings (highlighted), Total Recommendations count, per-category counts (right-sizing, idle, reserved, storage).
- **Full filter bar:** Type (category), Risk Level, Min Savings, Confidence dropdowns.
- **Generation targeting:** All resources with monthly spend above configurable threshold (default $50/mo) qualify. Daily run processes sorted by current-month spend descending — highest spenders first. When daily call limit hit mid-run, stops cleanly. Daily run replaces previous recommendations — users always see today's fresh set (old ones overwritten).
- **LLM provider:** Primary is Anthropic Claude Sonnet 4.6. Model is admin-configurable. Azure OpenAI is available as fallback provider.
- **Fallback trigger:** Claude's discretion (retry transient errors, fall back on availability/rate-limit failures).
- **Prompt data per call:** resource name, resource type, resource group, subscription, service category, last 30 days of billed cost.
- **Output structure:** JSON via tool use / structured output — forced structured JSON for reliable parsing, not free-text extraction.
- **Required output fields:** category (right-sizing/idle/reserved/storage), plain-language explanation, estimated monthly savings, confidence score (0–100).
- **Limit/cache transparency:** When daily call limit reached, show banner: "Daily recommendation limit reached. New recommendations will generate tomorrow." Cache is invisible to users — no "Generated: [date]" labels or cache indicators on cards.
- **Empty state:** Show empty state with manual trigger button for admins — useful for setup/testing/first-day before scheduled job has run.

### Claude's Discretion

- Fallback trigger logic (retry policy, error classification, failover threshold)
- Admin LLM usage visibility (whether to surface in Settings or just logs)
- Exact card spacing, typography, and visual polish
- Loading skeleton design
- Error states (LLM API down, Redis unavailable)
- Cost trend visualization format within cards (bar chart, sparkline, or plain numbers)

### Deferred Ideas (OUT OF SCOPE)

- Apply Now / Schedule / Dismiss buttons on cards — v2 scope (AI-05)
- Realized savings tracking — v2 scope (AI-06)
- "Applied This Month" stat in summary row — requires v2 acceptance tracking
- Bulk selection + "Apply Selected" — v2 scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-01 | System generates LLM-powered optimization recommendations on a daily schedule (Azure OpenAI primary, Anthropic Claude fallback — NOTE: user decision overrides this to Anthropic as primary) | APScheduler CronTrigger daily job; existing scheduler.py pattern extended; `run_recommendations` function registered in lifespan |
| AI-02 | Each recommendation includes: category (right-sizing/idle/reserved/storage), plain-language explanation, estimated monthly savings, and confidence score (0–100) | Anthropic tool_use with `tool_choice={"type":"tool","name":"record_recommendation"}` forces structured JSON output matching this schema |
| AI-03 | LLM responses are cached in Redis with 24-hour TTL to minimize API costs | redis-py `redis.asyncio` — `await redis.get(key)` / `await redis.set(key, value, ex=86400)`; connection initialized in lifespan |
| AI-04 | System enforces a configurable daily LLM call limit (default: 100 calls/day) | Redis atomic counter: `INCR` + `EXPIREAT midnight` pattern; counter checked before each LLM call |
</phase_requirements>

---

## Summary

Phase 5 adds a daily-scheduled LLM pipeline that queries each qualifying Azure resource against Anthropic Claude Sonnet 4.6, stores structured recommendations in PostgreSQL, caches LLM responses in Redis (24hr TTL), and enforces a configurable daily call cap. The frontend adds a `/recommendations` page with a card-based UI matching the reference design.

The technical implementation follows patterns already established in this codebase: APScheduler with `AsyncIOScheduler` (already running for ingestion), PostgreSQL via SQLAlchemy async (same session pattern as billing/anomaly), Redis 7 already in docker-compose, and TanStack Query + shadcn/ui service hooks on the frontend. The Anthropic Python SDK `tool_choice` pattern forces structured JSON from the LLM, making the output reliable without string parsing.

The primary novel complexity is the LLM integration: structured output via tool_use, a Redis-backed deduplication cache keyed on resource identity, and the daily call counter with midnight TTL reset. The Azure OpenAI fallback is a second client that is invoked only when the primary fails with a non-transient error (or after N retries on transient errors).

**Primary recommendation:** Wire the existing APScheduler instance with a new daily CronTrigger job; use the Anthropic SDK `client.messages.create()` with `tool_choice={"type":"tool","name":"record_recommendation"}` to guarantee structured output; store recommendations in a `recommendations` table with a `generated_date` column for daily-replace semantics; use `redis.asyncio` for both the response cache and the daily call counter.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | latest (>=0.40) | Anthropic Claude SDK — async client, tool_use structured output | Official Python SDK; `AsyncAnthropic` client for use in async FastAPI context |
| redis-py | >=5.0 | Redis client with built-in asyncio support (`redis.asyncio`) | aioredis was merged into redis-py; `redis.asyncio` is the current canonical async path — no separate aioredis package needed |
| APScheduler | 3.11.2 (already installed) | Daily CronTrigger job | Already in requirements.txt; existing scheduler.py singleton used — add new job, no new infrastructure |
| SQLAlchemy async | >=2.0 (already installed) | ORM for recommendations table | Identical to existing billing/anomaly pattern |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tenacity | already installed | Retry logic for transient LLM/network errors | Already in requirements.txt; use `@retry(wait=wait_exponential(...), stop=stop_after_attempt(3))` around LLM calls |
| pydantic-settings | already installed | Config: ANTHROPIC_API_KEY, AZURE_OPENAI_*, LLM_DAILY_CALL_LIMIT, LLM_MIN_MONTHLY_SPEND_THRESHOLD | Same Settings class, add new fields |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| redis.asyncio direct | fastapi-cache decorator library | Direct gives full control over cache key structure and invalidation; decorator library hides the daily-replace logic needed here |
| Anthropic tool_use | Instructor library | Instructor is a wrapper over tool_use — adds a dependency without additional benefit when the JSON schema is simple and fixed |
| CronTrigger daily | IntervalTrigger 24h | CronTrigger allows specifying exact UTC hour (e.g., 02:00) for predictable daily timing; interval accumulates drift |

**Installation (additions to requirements.txt):**
```bash
anthropic>=0.40
redis>=5.0
```

---

## Architecture Patterns

### Recommended Project Structure (additions)

```
backend/app/
├── models/
│   └── recommendation.py      # Recommendation SQLAlchemy model (new)
├── schemas/
│   └── recommendation.py      # Pydantic response schemas (new)
├── services/
│   └── recommendation.py      # LLM call, cache, daily-replace logic (new)
├── api/v1/
│   └── recommendation.py      # FastAPI router (new)
├── core/
│   ├── config.py              # Add ANTHROPIC_API_KEY, LLM_* settings
│   ├── redis.py               # Redis async client singleton (new)
│   └── scheduler.py           # Add daily recommendation job (existing, extend)
└── main.py                    # Add Redis lifespan init + recommendation job

frontend/src/
├── pages/
│   └── RecommendationsPage.tsx  # New page
├── services/
│   └── recommendation.ts       # TanStack Query hooks (new)
```

### Pattern 1: Anthropic Tool Use for Forced Structured Output

**What:** Pass a `tool_choice={"type": "tool", "name": "record_recommendation"}` with a single tool whose `input_schema` defines all required output fields. Claude is forced to call this tool, returning structured JSON in `response.content[0].input` (or the first tool_use block's `.input`).

**When to use:** Any time a single reliable JSON object must come back from Claude. No string parsing, no regex, no retries for malformed output.

**Example:**
```python
# Source: Official Anthropic tool use docs (platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use)
import anthropic

RECOMMENDATION_TOOL = {
    "name": "record_recommendation",
    "description": (
        "Record a cloud cost optimization recommendation for the given resource. "
        "Always call this tool with the analysis results."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["right-sizing", "idle", "reserved", "storage"],
                "description": "The optimization category for this resource"
            },
            "explanation": {
                "type": "string",
                "description": "Plain-language explanation of the recommendation (2-4 sentences)"
            },
            "estimated_monthly_savings": {
                "type": "number",
                "description": "Estimated monthly savings in USD if recommendation is applied"
            },
            "confidence_score": {
                "type": "integer",
                "description": "Confidence in this recommendation, 0-100",
                "minimum": 0,
                "maximum": 100
            }
        },
        "required": ["category", "explanation", "estimated_monthly_savings", "confidence_score"]
    }
}

async def call_llm_for_resource(client: anthropic.AsyncAnthropic, resource_data: dict) -> dict:
    """Call Claude and extract structured recommendation. Returns tool input dict."""
    prompt = build_prompt(resource_data)  # resource name, type, group, sub, 30-day costs
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        tools=[RECOMMENDATION_TOOL],
        tool_choice={"type": "tool", "name": "record_recommendation"},
        messages=[{"role": "user", "content": prompt}],
    )
    # With tool_choice=tool, the first content block is always tool_use
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_recommendation":
            return block.input  # Dict with category, explanation, estimated_monthly_savings, confidence_score
    raise ValueError("No tool_use block found in response")  # Should never happen with tool_choice=tool
```

### Pattern 2: Redis Cache Keyed on Resource Identity

**What:** Cache key encodes the resource identity (subscription + resource_group + resource_name + date). On cache hit, skip the LLM call entirely and use stored JSON. TTL = 86400 seconds (24 hours).

**When to use:** Before every LLM call. Also implements the "same resource within 24 hours uses cache" requirement (AI-03).

**Example:**
```python
# Source: redis-py docs and redis.io/learn/develop/python/fastapi
import json
from datetime import date

def make_cache_key(subscription_id: str, resource_group: str, resource_name: str) -> str:
    today = date.today().isoformat()
    return f"rec:cache:{subscription_id}:{resource_group}:{resource_name}:{today}"

async def get_or_generate_recommendation(redis_client, llm_client, resource_data: dict) -> dict:
    key = make_cache_key(
        resource_data["subscription_id"],
        resource_data["resource_group"],
        resource_data["resource_name"],
    )
    cached = await redis_client.get(key)
    if cached:
        return json.loads(cached)

    result = await call_llm_for_resource(llm_client, resource_data)
    await redis_client.set(key, json.dumps(result), ex=86400)  # 24hr TTL
    return result
```

### Pattern 3: Daily Call Counter in Redis

**What:** An atomic Redis counter tracks LLM calls per day. Key expires at midnight UTC (using `EXPIREAT`). Each call increments the counter; if it hits the limit, the run stops.

**When to use:** Check counter before each LLM call. This satisfies AI-04.

**Example:**
```python
import redis.asyncio as redis
from datetime import datetime, timezone, timedelta

def daily_counter_key() -> str:
    today = datetime.now(timezone.utc).date().isoformat()
    return f"rec:daily_calls:{today}"

def midnight_expiry_timestamp() -> int:
    """Unix timestamp for next midnight UTC."""
    now = datetime.now(timezone.utc)
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(midnight.timestamp())

async def increment_and_check_limit(redis_client, limit: int) -> bool:
    """Atomically increment daily counter. Returns True if under limit, False if limit exceeded."""
    key = daily_counter_key()
    current = await redis_client.incr(key)
    if current == 1:
        # First call today: set expiry at midnight UTC
        await redis_client.expireat(key, midnight_expiry_timestamp())
    return current <= limit
```

### Pattern 4: Daily-Replace Recommendations (DELETE + INSERT per run)

**What:** Each daily run deletes all existing recommendations before inserting the new batch. Simple and correct: users always see today's fresh set. No complex upsert semantics needed since there is no user-modifiable status to preserve (v1 is read-only).

**When to use:** At the start of each recommendation generation run, delete all existing rows, then insert new ones as they are generated.

```python
from sqlalchemy import delete
from app.models.recommendation import Recommendation

async def clear_recommendations(session: AsyncSession) -> None:
    """Delete all existing recommendations before today's run."""
    await session.execute(delete(Recommendation))
    await session.commit()
```

### Pattern 5: Redis Client Initialization in Lifespan

**What:** Create one `redis.asyncio.Redis` client in the FastAPI lifespan and store it on `app.state`. Access via a dependency `get_redis()`.

**When to use:** Consistent with how the project handles database sessions (AsyncSessionLocal). Single shared connection pool, cleanly closed on shutdown.

**Example:**
```python
# main.py lifespan addition
import redis.asyncio as aioredis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Existing: recover stale runs, start scheduler
    ...
    # New: Redis client
    app.state.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    yield

    # Shutdown
    await app.state.redis.aclose()
    scheduler.shutdown(wait=False)

# core/redis.py
from fastapi import Request
import redis.asyncio as aioredis

async def get_redis(request: Request) -> aioredis.Redis:
    return request.app.state.redis
```

### Pattern 6: APScheduler CronTrigger Daily Job

**What:** Add a CronTrigger job to the existing scheduler singleton. The daily recommendation job runs at a fixed UTC time (e.g., 02:00 UTC, after Azure billing data is typically complete). This supplements the existing 4-hour ingestion interval job.

**When to use:** Register in `main.py` lifespan, same as the ingestion job.

```python
# main.py lifespan (extending existing pattern)
from apscheduler.triggers.cron import CronTrigger
from app.services.recommendation import run_recommendations

scheduler.add_job(
    run_recommendations,
    CronTrigger(hour=2, minute=0, timezone="UTC"),  # 02:00 UTC daily
    id="recommendation_daily",
    replace_existing=True,
)
```

### Pattern 7: Provider Fallback Logic (Claude's Discretion area)

**Recommended approach:** Wrap the Anthropic call with `tenacity` retries (already installed). Retry up to 3 times on `anthropic.APIStatusError` with status 429 (rate limit) or 5xx (server error). On `anthropic.APIConnectionError` retry once. If all retries exhausted, attempt Azure OpenAI with the same prompt. If Azure also fails, log error and skip the resource (do not count against daily limit on failure).

```python
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
import anthropic

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError)),
)
async def call_anthropic_with_retry(client: anthropic.AsyncAnthropic, **kwargs) -> dict:
    return await call_llm_for_resource(client, **kwargs)
```

### Anti-Patterns to Avoid

- **Parsing free-text LLM output with regex:** Use `tool_choice={"type":"tool","name":"..."}` instead. Regex against LLM output breaks on any phrasing variation.
- **Module-level Redis client:** Initialize in lifespan and store on `app.state`, not at import time. The same reason get_settings() is called at function-call time — allows testing without a live Redis.
- **Single-phase commit:** Do not commit each recommendation individually in the loop — batch via session accumulation and commit once at the end of the run (same as `upsert_anomaly` pattern).
- **Using the daily call counter after a failed LLM call:** Only increment the counter on a successful API call (one that returns a valid response, even if Claude returns low confidence). Failed calls (exception thrown) should not count against the limit.
- **Putting cost trend data in the DB:** Cost trend data for the card's comparison panel comes from existing `billing_records` at query time — not stored on the recommendation row. The recommendation API endpoint joins billing_records to compute the 30-day trend for each resource in the response.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | String parsing / regex against Claude response | Anthropic `tool_choice={"type":"tool","name":"..."}` | Guarantees schema compliance; Claude cannot produce malformed output |
| Redis async connection management | Custom connection pool class | `redis.asyncio.from_url()` + `app.state.redis` | Built-in pooling, proper async context management, aclose() |
| LLM retry logic | Custom retry loop with sleep | `tenacity` (already installed) | Handles exponential backoff, jitter, specific exception types |
| Daily counter reset | Cron job to reset a DB counter at midnight | Redis `INCR` + `EXPIREAT` midnight | Atomic, no race conditions, auto-expires without cleanup |
| JSON schema validation of LLM output | Manual dict key checking after response | Pydantic model in service layer validates tool input dict | Catches missing fields early with clear error messages |

**Key insight:** The tool_use forced-output pattern eliminates the most common LLM integration failure mode (parsing unreliable text). Every other complexity in this phase (caching, rate limiting, scheduling) maps cleanly to existing infrastructure.

---

## Common Pitfalls

### Pitfall 1: Wrong `tool_choice` for Forced Structured Output

**What goes wrong:** Using `tool_choice={"type":"any"}` instead of `{"type":"tool","name":"record_recommendation"}`. With `any`, Claude may call a different tool or none at all if it misinterprets the prompt.

**Why it happens:** Developers assume `any` is sufficient to force a tool call.

**How to avoid:** Always use `{"type":"tool","name":"your_tool_name"}` when you need a specific tool to be called every time. The API prefills the assistant turn to guarantee this.

**Warning signs:** Response has `stop_reason == "end_turn"` instead of `"tool_use"`.

---

### Pitfall 2: `tool_choice` Conflicts with Extended Thinking

**What goes wrong:** If `thinking` is enabled on the API call AND `tool_choice` is set to `tool` or `any`, the API returns a 400 error.

**Why it happens:** Extended thinking and forced tool use are mutually exclusive.

**How to avoid:** Do not enable extended thinking for the recommendation generation call. Standard tool_use without extended thinking is sufficient.

---

### Pitfall 3: redis.asyncio Client Not Awaiting `.aclose()`

**What goes wrong:** Redis connection pool is not closed on FastAPI shutdown, leading to resource warnings and potential connection leaks in tests.

**Why it happens:** Forgetting that `redis.asyncio.Redis` requires `await client.aclose()` (not `.close()`).

**How to avoid:** In lifespan cleanup (after `yield`): `await app.state.redis.aclose()`.

---

### Pitfall 4: Daily Replace Deletes During Active UI Queries

**What goes wrong:** DELETE-then-INSERT means there's a brief window with zero recommendations in the DB, which the UI may fetch and display as an empty state.

**Why it happens:** The daily job runs while users are active.

**How to avoid:** Wrap the entire DELETE + INSERT sequence in a single transaction. PostgreSQL's transaction isolation ensures the UI either sees all-old or all-new, never zero. The `session.commit()` at the end of the run atomically swaps. Alternatively, use a `generated_date` column and query only the latest date (no delete needed — query `WHERE generated_date = (SELECT MAX(generated_date) FROM recommendations)`). This is safer and recommended.

**Recommendation:** Use the `generated_date` pattern: no DELETE, just insert new rows with today's date, query by MAX(generated_date). The "replace" is logical, not physical. Keeps historical data intact for potential future use.

---

### Pitfall 5: APScheduler Scheduler Already Started

**What goes wrong:** Calling `scheduler.add_job()` before `scheduler.start()` is fine, but calling it after `scheduler.start()` is also fine (APScheduler supports dynamic job addition). However, the existing scheduler.py singleton is already started in lifespan — the recommendation job must be added in the same `lifespan` block before or after `scheduler.start()`.

**Why it happens:** Developers add the job outside the lifespan function.

**How to avoid:** Add both jobs (ingestion interval + recommendation cron) in `main.py`'s `lifespan` before calling `scheduler.start()`.

---

### Pitfall 6: Redis `decode_responses=True` Required

**What goes wrong:** Without `decode_responses=True`, `redis.asyncio.get()` returns bytes, not strings. `json.loads(b'...')` fails in Python < 3.9 or produces incorrect results.

**Why it happens:** Default redis-py returns bytes.

**How to avoid:** Always initialize: `aioredis.from_url(settings.REDIS_URL, decode_responses=True)`.

---

### Pitfall 7: LLM Call for Resource Already Covered by Cache Hit Counted Against Daily Limit

**What goes wrong:** Incrementing the daily call counter even when a cache hit is served. This wastes the daily budget.

**Why it happens:** Counter increment is not inside the "cache miss" branch.

**How to avoid:** Only call `increment_and_check_limit()` after confirming there is no cached result for the resource. Structure: check cache → if hit, return cached → else check limit → if under limit, call LLM → increment counter → cache result.

---

### Pitfall 8: Azure OpenAI Fallback SDK Confusion

**What goes wrong:** Azure OpenAI uses the `openai` Python SDK (not `anthropic`), with an `AzureOpenAI` client class and different API key env var names. The base_url and api_version are also required.

**Why it happens:** Developers assume both providers use the same client interface.

**How to avoid:** Keep a separate `azure_llm.py` module with `AsyncAzureOpenAI` client. The structured output pattern for Azure OpenAI uses `response_format={"type":"json_object"}` or function calling — slightly different from Anthropic tool_use but achieving the same result.

---

## Code Examples

Verified patterns from official sources:

### Anthropic Async Client Initialization

```python
# Source: Official Anthropic Python SDK (github.com/anthropics/anthropic-sdk-python)
import anthropic

# Async client — use in FastAPI/async contexts
client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

# Sync client — only in non-async contexts (avoid in FastAPI)
# client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
```

### Complete Recommendation Generation Function

```python
# Pattern: tool_choice forces structured output; tenacity handles retries
import json
import anthropic
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

RECOMMENDATION_TOOL = {
    "name": "record_recommendation",
    "description": "Record a cloud cost optimization recommendation. Always call this tool.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["right-sizing", "idle", "reserved", "storage"]
            },
            "explanation": {"type": "string"},
            "estimated_monthly_savings": {"type": "number"},
            "confidence_score": {"type": "integer", "minimum": 0, "maximum": 100}
        },
        "required": ["category", "explanation", "estimated_monthly_savings", "confidence_score"]
    }
}

def build_prompt(resource: dict) -> str:
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
        f"Provide a specific optimization recommendation."
    )

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)),
)
async def call_anthropic(client: anthropic.AsyncAnthropic, resource: dict) -> dict:
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        tools=[RECOMMENDATION_TOOL],
        tool_choice={"type": "tool", "name": "record_recommendation"},
        messages=[{"role": "user", "content": build_prompt(resource)}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_recommendation":
            return block.input
    raise ValueError("No tool_use block in response")
```

### Redis Async Setup

```python
# Source: redis.io/learn/develop/python/fastapi + redis-py docs
import redis.asyncio as aioredis

# In main.py lifespan:
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
app.state.redis = redis_client
# ... yield ...
await redis_client.aclose()

# Cache get/set:
cached_json = await redis_client.get(cache_key)   # Returns str or None
if cached_json:
    result = json.loads(cached_json)
else:
    result = await call_anthropic(...)
    await redis_client.set(cache_key, json.dumps(result), ex=86400)
```

### Recommendation SQLAlchemy Model

```python
# Pattern: follows billing.py — utcnow() redefined locally, UUID PK, indexes on query columns
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Integer, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)
    resource_name: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    meter_category: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)   # right-sizing|idle|reserved|storage
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    estimated_monthly_savings: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    current_monthly_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # for comparison panel
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    __table_args__ = (
        Index("idx_recommendation_generated_date", "generated_date"),
        Index("idx_recommendation_category", "category"),
    )
```

### Recommendation Query (Latest Date Pattern)

```python
# Service layer: always return today's (or most recent) recommendations
from sqlalchemy import select, func

async def get_latest_recommendations(session: AsyncSession) -> list:
    # Get the most recent generated_date
    max_date_stmt = select(func.max(Recommendation.generated_date))
    latest_date = (await session.execute(max_date_stmt)).scalar()
    if latest_date is None:
        return []
    stmt = (
        select(Recommendation)
        .where(Recommendation.generated_date == latest_date)
        .order_by(Recommendation.estimated_monthly_savings.desc())
    )
    return (await session.execute(stmt)).scalars().all()
```

### Frontend Service Hook (follows anomaly.ts pattern exactly)

```typescript
// frontend/src/services/recommendation.ts
import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

export interface Recommendation {
  id: string;
  generated_date: string;
  resource_name: string;
  resource_group: string;
  subscription_id: string;
  service_name: string;
  meter_category: string;
  category: 'right-sizing' | 'idle' | 'reserved' | 'storage';
  explanation: string;
  estimated_monthly_savings: number;
  confidence_score: number;
  current_monthly_cost: number;
  created_at: string;
}

export interface RecommendationSummary {
  total_count: number;
  potential_monthly_savings: number;
  by_category: Record<string, number>;
  daily_limit_reached: boolean;
  calls_used_today: number;
  daily_call_limit: number;
}

export function useRecommendations(filters: Record<string, string | number | undefined> = {}) {
  return useQuery<Recommendation[]>({
    queryKey: ['recommendations', filters],
    queryFn: async () => {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== 'all')
      );
      const { data } = await api.get<Recommendation[]>('/recommendations/', { params });
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 min — recommendations change daily
  });
}

export function useRecommendationSummary() {
  return useQuery<RecommendationSummary>({
    queryKey: ['recommendation-summary'],
    queryFn: async () => {
      const { data } = await api.get<RecommendationSummary>('/recommendations/summary');
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| aioredis (separate package) | redis-py `redis.asyncio` submodule | redis-py 4.2+ (2022) | Single package; `import redis.asyncio as aioredis` is the migration path |
| Parsing LLM JSON with regex/try-except | `tool_choice` forced tool use | 2023 (Anthropic tool use launch) | Eliminates JSON parsing failures entirely |
| `@app.on_event("startup")` | `asynccontextmanager lifespan(app)` | FastAPI 0.93 (2023) | Already used in this project's main.py |
| Structured outputs beta (Nov 2025) | Tool use (stable) | — | Beta structured outputs require `anthropic-beta` header and only work with Sonnet 4.5/Opus 4.1; tool_use is stable and works on all models including Sonnet 4.6 |

**Deprecated/outdated:**
- `aioredis` package: superseded by `redis.asyncio` built into redis-py >= 4.2; do not add aioredis to requirements.txt
- Anthropic `@app.on_event("startup")` pattern: project already uses lifespan correctly
- `client.beta.messages.parse()` structured output beta: requires `anthropic-beta: structured-outputs-2025-11-13` header and is limited to Sonnet 4.5 / Opus 4.1 — not compatible with Sonnet 4.6. Use standard tool_use instead.

---

## Open Questions

1. **Azure OpenAI fallback credentials**
   - What we know: Settings.py already has `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
   - What's unclear: Azure OpenAI uses separate endpoint URL and API key from Azure Identity. The existing `azure-identity` package is for Cost Management, not OpenAI.
   - Recommendation: Add `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_API_KEY` to Settings. Use the `openai` Python SDK with `AsyncAzureOpenAI`. Add `openai>=1.0` to requirements.txt only when implementing fallback. If admin never configures these vars, fallback silently no-ops (logs warning, skips).

2. **Cost trend data shape for UI comparison panel**
   - What we know: The card must show current → recommended comparison with billing cost trend data. `billing_records` has this data grouped by resource_name + resource_group.
   - What's unclear: Whether the comparison panel needs an aggregate (30-day total, monthly average) or a time-series array. An array adds API payload size; a scalar is simpler.
   - Recommendation: Return `current_monthly_cost` as a scalar on the recommendation row (stored at generation time from last 30 days). The comparison panel shows "Current: $X/mo → Recommended: $(X - savings)/mo". If a sparkline is desired, the API can compute it on-demand from billing_records — but keep it optional. Default to scalars.

3. **Admin manual trigger endpoint mechanics**
   - What we know: Empty state requires a manual trigger button for admins.
   - What's unclear: Should the manual trigger use the same `asyncio.create_task` fire-and-forget pattern as ingestion (`/api/v1/ingestion/run`), or wait for completion?
   - Recommendation: Use `asyncio.create_task` (fire-and-forget) identical to ingestion pattern. Return 202 Accepted immediately. The page will refresh via TanStack Query refetch after a few seconds.

4. **`openai` package version conflict**
   - What we know: `azure-mgmt-costmanagement` and `azure-identity` are already installed.
   - What's unclear: Does any existing dependency transitively require `openai`?
   - Recommendation: Run `pip show openai` in the container to check. If not present, add `openai>=1.50` for Azure fallback (the async client is `AsyncAzureOpenAI`).

---

## Sources

### Primary (HIGH confidence)

- Anthropic official tool use documentation — `platform.claude.com/docs/en/agents-and-tools/tool-use/implement-tool-use` — tool_choice semantics, input_schema, forced tool call pattern, Python SDK examples verified
- Anthropic cookbook — `github.com/anthropics/anthropic-cookbook/blob/main/tool_use/extracting_structured_json.ipynb` — tool_use for structured JSON extraction pattern verified
- redis-py official docs — redis.io/learn/develop/python/fastapi — `redis.asyncio.from_url()`, `decode_responses`, `set(key, value, ex=TTL)`, `aclose()` pattern verified
- Codebase direct inspection — `backend/app/core/scheduler.py`, `backend/app/main.py`, `backend/requirements.txt`, `backend/app/services/anomaly.py`, `frontend/src/services/anomaly.ts` — all established project patterns verified from source

### Secondary (MEDIUM confidence)

- APScheduler 3.11.2 docs — `apscheduler.readthedocs.io/en/3.x/userguide.html` — CronTrigger, AsyncIOScheduler — consistent with existing scheduler.py usage
- Multiple WebSearch results (2025) confirming `redis.asyncio` as the correct async path, aioredis deprecation status

### Tertiary (LOW confidence)

- Anthropic Structured Outputs beta (Nov 2025) — mentioned in search results but NOT recommended here because it requires `anthropic-beta` header and is limited to Sonnet 4.5/Opus 4.1, not Sonnet 4.6 (the chosen model). Standard tool_use is the stable, correct approach.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against existing requirements.txt and official docs; redis-py and anthropic SDK are well-established
- Architecture: HIGH — patterns derived directly from existing codebase (anomaly.py, ingestion.py, scheduler.py, main.py) with verified LLM integration pattern from official Anthropic cookbook
- Pitfalls: HIGH (tool_choice, Redis decode, lifespan) / MEDIUM (Azure fallback, provider compatibility) — most verified against official docs; fallback complexity is inherent

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days — stable libraries; Anthropic SDK moves fast but tool_use pattern is stable)
