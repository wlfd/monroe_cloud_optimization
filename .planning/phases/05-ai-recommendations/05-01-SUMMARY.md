---
phase: 05-ai-recommendations
plan: "01"
subsystem: database
tags: [anthropic, redis, alembic, sqlalchemy, postgresql, recommendations]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    provides: billing.py model pattern (utcnow, UUID PK, Mapped columns, __table_args__), anomalies table migration chain

provides:
  - recommendations PostgreSQL table with 13 columns and 3 indexes
  - get_redis FastAPI dependency (backend/app/core/redis.py)
  - LLM/AI config fields in Settings (ANTHROPIC_API_KEY, LLM_DAILY_CALL_LIMIT, etc.)
  - anthropic and redis packages declared in requirements.txt

affects: [05-02, 05-03, 05-04, 05-05]

# Tech tracking
tech-stack:
  added: [anthropic>=0.40, redis>=5.0 (async)]
  patterns: [utcnow() redefined locally per model file, get_redis dependency from app.state.redis]

key-files:
  created:
    - backend/app/models/recommendation.py
    - backend/app/core/redis.py
    - backend/migrations/versions/e7846b8acf35_add_recommendations_table.py
  modified:
    - backend/requirements.txt
    - backend/app/core/config.py
    - backend/migrations/env.py

key-decisions:
  - "utcnow() helper redefined locally in recommendation.py — keeps model files decoupled, consistent with billing.py pattern"
  - "get_redis returns app.state.redis — Redis client must be initialized in main.py lifespan before this dependency is usable"
  - "generated_date as Date (not DateTime) — daily-replace semantics: service queries WHERE generated_date = MAX(generated_date)"
  - "confidence_score as Integer (not Numeric) — LLM outputs integer 0-100 scale, not fractional"

patterns-established:
  - "Pattern: Redis dependency via app.state.redis — initialize in lifespan, inject via get_redis(request: Request)"
  - "Pattern: Migration env.py must import all model modules — alembic autogenerate only detects models loaded at import time"

requirements-completed: [AI-01, AI-03, AI-04]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 5 Plan 01: AI Recommendations Infrastructure Summary

**Recommendations PostgreSQL table, Redis async client dependency, and LLM config fields establishing the foundation for AI-powered cost optimization in Phase 5**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T16:34:05Z
- **Completed:** 2026-02-21T16:36:20Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Created `recommendations` table via Alembic migration with 13 columns (UUID PK, generated_date, 5 resource identity columns, 4 LLM output fields, current_monthly_cost, created_at) and 3 indexes
- Created `backend/app/core/redis.py` with `get_redis` FastAPI dependency returning `app.state.redis`
- Added 7 LLM/AI config fields to Settings: ANTHROPIC_API_KEY, ANTHROPIC_MODEL, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT, LLM_DAILY_CALL_LIMIT, LLM_MIN_MONTHLY_SPEND_THRESHOLD
- Declared `anthropic>=0.40` and `redis>=5.0` in requirements.txt

## Task Commits

Each task was committed atomically:

1. **Task 1: Install dependencies, extend config, create Redis singleton** - `d440413` (feat)
2. **Task 2: Create Recommendation model and Alembic migration** - `8e57870` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/requirements.txt` - Added anthropic>=0.40 and redis>=5.0
- `backend/app/core/config.py` - Added 7 LLM/AI config fields after MOCK_AZURE block
- `backend/app/core/redis.py` - New: get_redis FastAPI dependency returning app.state.redis
- `backend/app/models/recommendation.py` - New: Recommendation ORM model following billing.py pattern
- `backend/migrations/versions/e7846b8acf35_add_recommendations_table.py` - New: Alembic migration creating recommendations table
- `backend/migrations/env.py` - Added recommendation import for autogenerate

## Decisions Made
- utcnow() helper redefined locally in recommendation.py — consistent with billing.py and ingestion model files; keeps model files decoupled
- get_redis returns app.state.redis from the request — Redis client must be initialized in main.py lifespan before use (handled in 05-02 or already present)
- generated_date column is Date (not DateTime) — daily-replace semantics; service layer queries MAX(generated_date)
- confidence_score as Integer (not Numeric) — LLM outputs 0-100 scale integers

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added recommendation import to migrations/env.py**
- **Found during:** Task 2 (Alembic autogenerate)
- **Issue:** env.py did not import `from app.models import recommendation` — autogenerate produced `pass` migration (detected no new tables)
- **Fix:** Added `from app.models import recommendation  # noqa: F401` to env.py; also wrote the updated env.py directly to container since migrations/ is not mounted as a volume
- **Files modified:** backend/migrations/env.py
- **Verification:** Reran autogenerate — detected 'recommendations' table and all 3 indexes; `alembic upgrade head` completed without error; `alembic current` shows `e7846b8acf35 (head)`
- **Committed in:** 8e57870 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (blocking)
**Impact on plan:** Necessary fix — Alembic autogenerate cannot detect models not imported in env.py. No scope creep.

## Issues Encountered
- Docker volume mapping: `./backend/app` is mounted to `/code/app` but `./backend/migrations` is NOT mounted. The updated env.py had to be written directly into the running container, then the migration file was copied back via `docker cp`. This is an expected constraint of the dev setup.

## User Setup Required
None - no external service configuration required beyond what is already in .env.local.

Note: ANTHROPIC_API_KEY and AZURE_OPENAI_* fields are present in config but will only be needed when the recommendation service (05-02) is implemented. They default to empty strings.

## Next Phase Readiness
- recommendations table exists in PostgreSQL with all 13 columns and 3 indexes
- `get_redis` dependency importable from `app.core.redis`
- Config has all required LLM fields
- anthropic and redis packages declared; will be installed when container rebuilds
- Ready for 05-02: LLM recommendation service implementation

---
*Phase: 05-ai-recommendations*
*Completed: 2026-02-21*
