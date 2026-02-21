---
phase: 05-ai-recommendations
plan: "02"
subsystem: ai-service
tags: [anthropic, redis, apscheduler, fastapi, llm, recommendations]

# Dependency graph
requires:
  - phase: 05-ai-recommendations
    plan: "01"
    provides: recommendations table, get_redis dependency, LLM config fields, anthropic/redis packages

provides:
  - LLM recommendation generation pipeline (Anthropic primary + Azure OpenAI fallback)
  - Redis cache per resource (24hr TTL) — AI-03
  - Daily call counter via Redis INCR+EXPIREAT — AI-04
  - GET /api/v1/recommendations/ (filterable list)
  - GET /api/v1/recommendations/summary (stats + daily limit status)
  - POST /api/v1/recommendations/run (admin, 202, fire-and-forget)
  - APScheduler CronTrigger daily job at 02:00 UTC
  - Redis lifespan init (app.state.redis) and aclose() in main.py

affects: [05-03, 05-04, 05-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "tool_choice forced structured output via Anthropic tools API (AI-02)"
    - "Redis INCR+EXPIREAT pattern for daily call counter reset at midnight UTC"
    - "MAX(generated_date) subquery for logical daily-replace without DELETE"
    - "fire-and-forget via asyncio.create_task for POST /run admin trigger"
    - "tenacity @retry with retry_if_exception_type for transient LLM errors"

key-files:
  created:
    - backend/app/schemas/recommendation.py
    - backend/app/services/recommendation.py
    - backend/app/api/v1/recommendation.py
  modified:
    - backend/app/api/v1/router.py
    - backend/app/main.py

key-decisions:
  - "require_admin imported from app.api.v1.ingestion (not app.api.v1.auth) — that is where require_admin is defined in this codebase"
  - "get_db imported from app.core.dependencies (consistent with anomaly.py and auth.py patterns)"
  - "anthropic and redis packages installed manually into running container — container was built before Phase 5 Plan 01 added them to requirements.txt; rebuild needed in deployment"
  - "Azure OpenAI fallback is graceful no-op when AZURE_OPENAI_ENDPOINT/KEY unset — logs warning and returns None"
  - "Daily limit counter incremented before LLM call, not after — prevents races; cache hits bypass counter entirely"

# Metrics
duration: 3min
completed: 2026-02-21
---

# Phase 5 Plan 02: AI Recommendation Pipeline Summary

**Anthropic Claude Sonnet 4.6 LLM pipeline with Redis caching, daily call counter, Azure OpenAI fallback, and three FastAPI endpoints for listing, summarizing, and triggering recommendations**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T16:39:11Z
- **Completed:** 2026-02-21T16:41:25Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `backend/app/schemas/recommendation.py` with `RecommendationOut` and `RecommendationSummary` Pydantic models
- Created `backend/app/services/recommendation.py`: complete LLM recommendation pipeline
  - `RECOMMENDATION_TOOL` with tool_choice forced structured output (AI-02): category, explanation, estimated_monthly_savings, confidence_score
  - Redis cache per resource keyed on `rec:cache:{subscription_id}:{resource_group}:{resource_name}:{date}` with 24hr TTL (AI-03)
  - Daily call counter via `Redis INCR + EXPIREAT midnight` pattern (AI-04)
  - `_call_anthropic` with tenacity @retry (3 attempts, exponential 2-30s backoff) on RateLimitError, InternalServerError, APIConnectionError
  - `_call_azure_openai` fallback: graceful no-op if AZURE_OPENAI_ENDPOINT/KEY unset
  - `run_recommendations`: qualifies resources by monthly spend >= threshold, sorted by spend desc (highest spenders first when limit hit)
  - `get_latest_recommendations`: MAX(generated_date) subquery with category/min_savings/min_confidence filters
  - `get_recommendation_summary`: total count, potential savings, per-category counts, daily limit status
- Created `backend/app/api/v1/recommendation.py`:
  - `GET /` → `list_recommendations` (filterable, no auth guard — read-only)
  - `GET /summary` → `recommendation_summary`
  - `POST /run` → `trigger_recommendations` (admin-only via `require_admin`, 202, fire-and-forget via `asyncio.create_task`)
- Updated `backend/app/api/v1/router.py`: added recommendation router at `/recommendations` prefix with `tags=["recommendations"]`
- Updated `backend/app/main.py`:
  - Initialize `app.state.redis = aioredis.from_url(...)` in lifespan startup
  - Register `CronTrigger(hour=2, minute=0, timezone="UTC")` daily recommendation job
  - `await app.state.redis.aclose()` on shutdown

## Task Commits

Each task was committed atomically:

1. **Task 1: Recommendation service (LLM pipeline, cache, counter, CRUD)** - `f1bb53d` (feat)
2. **Task 2: FastAPI router, lifespan wiring, and scheduler job** - `2782363` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/app/schemas/recommendation.py` - New: RecommendationOut, RecommendationSummary Pydantic models
- `backend/app/services/recommendation.py` - New: full LLM pipeline service (311 lines)
- `backend/app/api/v1/recommendation.py` - New: GET /, GET /summary, POST /run endpoints
- `backend/app/api/v1/router.py` - Added recommendation router at /recommendations
- `backend/app/main.py` - Redis lifespan init/close, daily CronTrigger job at 02:00 UTC

## Decisions Made

- `require_admin` imported from `app.api.v1.ingestion` — this is where it is defined; the plan incorrectly referenced `app.api.v1.auth`. Auto-corrected to match the actual codebase (Rule 1).
- `get_db` imported from `app.core.dependencies` — consistent with anomaly.py and auth.py.
- Azure OpenAI fallback is a graceful no-op when AZURE_OPENAI_ENDPOINT/KEY are unset — logs warning and returns None.
- Daily limit counter is incremented before LLM call — prevents races; cache hits bypass the counter entirely.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed anthropic and redis packages into running container**
- **Found during:** Task 1 verification
- **Issue:** `anthropic>=0.40` and `redis>=5.0` are declared in requirements.txt (added in Phase 5 Plan 01) but were not installed in the running container, which was built before those additions
- **Fix:** Ran `pip install "anthropic>=0.40" "redis>=5.0"` inside the running container. The container will get them on next rebuild. This is an expected constraint of the dev setup (same pattern as the Phase 5 Plan 01 migrations/env.py fix)
- **Files modified:** None (runtime fix)
- **Commit:** N/A (runtime install)

**2. [Rule 1 - Bug] Corrected require_admin import path**
- **Found during:** Task 2 implementation
- **Issue:** Plan specified `from app.api.v1.auth import require_admin` but `require_admin` is defined in `app.api.v1.ingestion`, not `app.api.v1.auth`
- **Fix:** Used `from app.api.v1.ingestion import require_admin` — the actual location in this codebase
- **Files modified:** backend/app/api/v1/recommendation.py
- **Commit:** 2782363

---

**Total deviations:** 2 auto-fixed (1 blocking runtime install, 1 bug in plan spec)
**Impact on plan:** Both resolved without scope creep. All success criteria met.

## Self-Check: PASSED

Files created/modified:
- FOUND: backend/app/schemas/recommendation.py
- FOUND: backend/app/services/recommendation.py
- FOUND: backend/app/api/v1/recommendation.py
- FOUND: backend/app/api/v1/router.py
- FOUND: backend/app/main.py

Commits:
- FOUND: f1bb53d (Task 1: recommendation service and schemas)
- FOUND: 2782363 (Task 2: router, lifespan, and scheduler)

Verification results:
- `RECOMMENDATION_TOOL['name']` = `record_recommendation` ✓
- `len(router.routes)` = 3 ✓
- `recommendation_daily` in main.py ✓
- `app.state.redis` in main.py ✓
- `aclose` in main.py ✓
- `/recommendations` in router.py ✓

## Next Phase Readiness

- POST /api/v1/recommendations/run (admin) triggers generation with ANTHROPIC_API_KEY set
- GET /api/v1/recommendations/ returns latest batch filtered by category/min_savings/min_confidence
- GET /api/v1/recommendations/summary returns KPI stats and daily limit status
- Redis initialized in lifespan — get_redis dependency fully usable
- Daily CronTrigger job registered at 02:00 UTC
- Ready for 05-03: Frontend recommendations page

---
*Phase: 05-ai-recommendations*
*Completed: 2026-02-21*
