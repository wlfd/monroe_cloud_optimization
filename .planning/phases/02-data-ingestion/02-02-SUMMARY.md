---
phase: 02-data-ingestion
plan: "02"
subsystem: api
tags: [azure, cost-management, tenacity, sqlalchemy, asyncio, postgresql, ingestion]

# Dependency graph
requires:
  - phase: 02-01
    provides: BillingRecord, IngestionRun, IngestionAlert models + Alembic migration applied
  - phase: 02-01
    provides: AZURE_SUBSCRIPTION_ID, AZURE_SUBSCRIPTION_SCOPE, MOCK_AZURE settings in config.py
provides:
  - azure_client.py: Azure Cost Management API wrapper with retry, pagination, mock mode
  - fetch_with_retry: tenacity retry with 5s/30s/120s wait chain (INGEST-03)
  - fetch_billing_data: async fetch with MOCK_AZURE synthetic data path
  - ingestion.py: full ingestion orchestration service
  - run_ingestion: public entry point with asyncio.Lock concurrency guard
  - compute_delta_window: 7-day cap + 24h overlap for late-arriving records
  - upsert_billing_records: pg_insert ON CONFLICT DO UPDATE — idempotent
  - run_backfill: 24 monthly chunks with asyncio.sleep(1) QPU throttle
  - create_ingestion_alert / clear_active_alerts: alert lifecycle management
  - log_ingestion_run: IngestionRun row creation with final status
  - recover_stale_runs: startup recovery for crashed 'running' rows
affects:
  - 02-03 (scheduler wires run_ingestion into APScheduler)
  - 02-03 (API endpoints expose run_ingestion trigger + ingestion status)
  - 02-04 (tests target these service functions directly)

# Tech tracking
tech-stack:
  added:
    - azure-mgmt-costmanagement (Azure Cost Management SDK)
    - azure-identity (DefaultAzureCredential)
    - tenacity (retry with wait_chain)
    - httpx (pagination safety net, already installed)
  patterns:
    - asyncio.to_thread wrapping for synchronous SDK calls (event-loop safety)
    - pg_insert().on_conflict_do_update() for idempotent billing upserts
    - asyncio.Lock as concurrency guard (module-level singleton)
    - get_settings() called at function-call time (not module import) for testability
    - AsyncSessionLocal used directly in service layer (not get_db dependency)

key-files:
  created:
    - backend/app/services/__init__.py
    - backend/app/services/azure_client.py
    - backend/app/services/ingestion.py
  modified: []

key-decisions:
  - "24h overlap applied to delta window start to catch late-arriving Azure records (resolves open question from research, Pattern 6)"
  - "MAX_CATCHUP_DAYS=7 caps delta window after outage to avoid API overload"
  - "MOCK_AZURE check via get_settings() at call time (not module-level settings import) — required for test cache invalidation"
  - "AsyncSessionLocal used in service layer directly — scheduler jobs run outside request context (Pattern 7 from research)"
  - "Pagination not followed for MVP — chunked weekly date windows keep pages small"
  - "Error session opened fresh in _do_ingestion exception handler to avoid using a potentially corrupt session"

patterns-established:
  - "Async services call get_settings() at function scope, not module scope — allows cache_clear() in tests"
  - "All Azure SDK calls wrapped in asyncio.to_thread — never call synchronous SDK in async context"
  - "ON CONFLICT DO UPDATE via pg_insert — all ingestion writes are idempotent"

requirements-completed: [INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06]

# Metrics
duration: 3min
completed: 2026-02-20
---

# Phase 2 Plan 02: Azure Client + Ingestion Service Summary

**Azure Cost Management API client with tenacity retry (5s/30s/120s), idempotent pg_insert upsert, 24-month chunked backfill, asyncio concurrency guard, and full alert/run-logging lifecycle**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T00:57:37Z
- **Completed:** 2026-02-21T01:00:39Z
- **Tasks:** 2
- **Files modified:** 3 created

## Accomplishments
- azure_client.py: fetch_billing_data with MOCK_AZURE synthetic path + real Azure SDK path (asyncio.to_thread wrapped), fetch_with_retry with exact 5s/30s/120s tenacity chain, pagination safety net via httpx
- ingestion.py: full orchestration — delta window (7-day cap + 24h overlap), idempotent pg_insert ON CONFLICT upsert, 24-month chunked backfill with QPU throttle, alert create/clear, run logging, startup stale-run recovery
- run_ingestion() concurrency guard using asyncio.Lock — concurrent calls return immediately without starting a second run

## Task Commits

Each task was committed atomically:

1. **Task 1: Azure client — fetch, pagination, retry, mock mode** - `57a84b3` (feat)
2. **Task 2: Ingestion service — orchestration, delta window, upsert, backfill, alerts, run logging** - `4649f32` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/app/services/__init__.py` - Empty package marker
- `backend/app/services/azure_client.py` - Azure Cost Management wrapper: _build_client, _fetch_page_sync (asyncio.to_thread), _fetch_next_page_sync (httpx pagination), fetch_billing_data (mock + real), fetch_with_retry (tenacity)
- `backend/app/services/ingestion.py` - Full ingestion orchestration: concurrency guard, get_last_successful_run, compute_delta_window, upsert_billing_records (pg_insert ON CONFLICT), log_ingestion_run, create_ingestion_alert, clear_active_alerts, recover_stale_runs, run_backfill, _do_ingestion, run_ingestion

## Decisions Made
- **24h overlap on delta window start:** Resolves the open question from research — applies Pattern 6 (24h re-check) to catch late-arriving Azure records
- **get_settings() at call time not import time:** Required so tests can call `get_settings.cache_clear()` + set env vars and get fresh settings in the same process; avoids stale module-level singleton
- **Fresh error session in exception handler:** _do_ingestion opens a new AsyncSessionLocal in the except block to log the failed run — prevents using a potentially dirty/rolled-back session for error recording
- **Pagination not followed for MVP:** Chunked weekly date windows keep individual responses small; _fetch_next_page_sync exists as safety net only

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Changed settings import from module-level to call-time**
- **Found during:** Task 1 (azure_client.py verification)
- **Issue:** Plan specified `from app.core.config import settings` at module level; the verify script sets `os.environ['MOCK_AZURE'] = 'true'` and calls `get_settings.cache_clear()` after the module is already loaded — the old `settings` singleton still reads `MOCK_AZURE=False`, causing the code to fall into the real Azure path and crash with `AttributeError: 'NoneType' has no attribute 'isoformat'`
- **Fix:** Changed import to `from app.core.config import get_settings` and added `settings = get_settings()` inside `fetch_billing_data` — settings are re-fetched at call time, respecting cache invalidation
- **Files modified:** backend/app/services/azure_client.py
- **Verification:** `asyncio.run(fetch_billing_data('/subscriptions/test', None, None))` returns 3 synthetic records
- **Committed in:** 57a84b3 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added fresh error session in _do_ingestion exception handler**
- **Found during:** Task 2 (ingestion.py implementation)
- **Issue:** The plan's exception block reused the same `session` that raised the exception — SQLAlchemy async sessions that raise exceptions are in an invalid state and cannot safely execute further queries
- **Fix:** Exception handler opens a fresh `AsyncSessionLocal()` context for log_ingestion_run and create_ingestion_alert calls
- **Files modified:** backend/app/services/ingestion.py
- **Verification:** Import test passes cleanly; logic ensures error path has a clean session
- **Committed in:** 4649f32 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes required for correct operation. No scope creep. Must-have behaviors all satisfied.

## Issues Encountered
- Docker image required rebuild (`docker compose build api`) after new requirements (azure-mgmt-costmanagement, azure-identity, tenacity) were not present in the previously built image. Rebuilt successfully.

## User Setup Required
None - no external service configuration required for development (MOCK_AZURE=True in .env.local bypasses Azure credentials).

## Next Phase Readiness
- azure_client.py and ingestion.py are the engine Plan 03 wires into the scheduler and API
- Scheduler (Plan 03) imports `run_ingestion` and `recover_stale_runs` from ingestion.py
- API endpoints (Plan 03) import `run_ingestion`, `is_ingestion_running`, `get_last_successful_run`
- No blockers

---
*Phase: 02-data-ingestion*
*Completed: 2026-02-20*
