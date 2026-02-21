---
phase: 02-data-ingestion
plan: "03"
subsystem: api
tags: [apscheduler, fastapi, lifespan, scheduler, ingestion, admin-api, pydantic]

# Dependency graph
requires:
  - phase: 02-02
    provides: run_ingestion, is_ingestion_running, recover_stale_runs functions in ingestion.py; IngestionRun, IngestionAlert models in billing.py
provides:
  - APScheduler AsyncIOScheduler singleton (max_instances=1, coalesce=True, UTC timezone)
  - FastAPI lifespan context manager: stale run recovery on startup, 4-hour interval job registration, clean scheduler shutdown
  - Ingestion admin API: POST /run, GET /status, GET /runs, GET /alerts
  - Pydantic response schemas: IngestionRunResponse, IngestionAlertResponse, IngestionStatusResponse, TriggerResponse
  - require_admin dependency enforcing role=='admin' with 403 on non-admin access
affects:
  - 03-cost-analysis
  - 04-recommendations
  - any phase that adds admin endpoints (shared require_admin pattern)

# Tech tracking
tech-stack:
  added:
    - APScheduler==3.11.2 (AsyncIOScheduler with MemoryJobStore)
  patterns:
    - FastAPI lifespan context manager for startup/shutdown side effects
    - Fire-and-forget ingestion via asyncio.create_task (non-blocking manual trigger)
    - require_admin dependency function (role-based access control pattern)
    - Scheduler singleton in core/ module, job registered in lifespan (not in scheduler.py)

key-files:
  created:
    - backend/app/core/scheduler.py
    - backend/app/schemas/ingestion.py
    - backend/app/api/v1/ingestion.py
  modified:
    - backend/app/main.py
    - backend/app/api/v1/router.py

key-decisions:
  - "scheduler.shutdown(wait=False) on FastAPI shutdown — avoids blocking shutdown for up to 4 hours if job in flight; asyncio.Lock in ingestion.py handles in-flight concurrency"
  - "asyncio.create_task for manual /run trigger — fire-and-forget pattern keeps HTTP response immediate while ingestion runs in background"
  - "require_admin as a dependency function (not decorator) — composable with get_current_user, consistent with FastAPI DI patterns"
  - "APScheduler _job_defaults is private in 3.11.x — job_defaults attribute removed from public API (discovered during verification)"

patterns-established:
  - "Pattern: Admin-only endpoints use require_admin = Depends(get_current_user) + role check + 403 raise"
  - "Pattern: Scheduler singleton in app/core/scheduler.py, job wiring in main.py lifespan — keeps scheduler.py clean"
  - "Pattern: Fire-and-forget background tasks use asyncio.create_task (not BackgroundTasks) for long-running jobs"

requirements-completed: [INGEST-01, INGEST-05, INGEST-06]

# Metrics
duration: 8min
completed: 2026-02-20
---

# Phase 2 Plan 03: Scheduler + Ingestion Admin API Summary

**APScheduler 4-hour recurring job wired into FastAPI lifespan with stale-run recovery, plus four admin-only ingestion management endpoints (/run, /status, /runs, /alerts)**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-21T01:03:26Z
- **Completed:** 2026-02-21T01:11:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- AsyncIOScheduler singleton (max_instances=1, coalesce=True) wired into FastAPI lifespan — fires run_ingestion every 4 hours automatically
- Stale 'running' run recovery on app startup prevents phantom running states after crash/restart
- Four admin-only REST endpoints for ingestion management with role-based access control (403 for non-admin)
- Pydantic response schemas mirror all IngestionRun and IngestionAlert model fields with from_attributes=True

## Task Commits

Each task was committed atomically:

1. **Task 1: APScheduler singleton + FastAPI lifespan integration + stale run cleanup** - `31064ba` (feat)
2. **Task 2: Ingestion admin API — /run, /status, /runs, /alerts endpoints + Pydantic schemas** - `1528f57` (feat)

**Plan metadata:** `[docs commit hash]` (docs: complete plan)

## Files Created/Modified
- `backend/app/core/scheduler.py` - AsyncIOScheduler singleton with job_defaults (coalesce, max_instances, misfire_grace_time)
- `backend/app/main.py` - FastAPI lifespan: recover_stale_runs on startup, register 4-hour job, start/stop scheduler
- `backend/app/schemas/ingestion.py` - Four Pydantic response models with from_attributes=True for ORM compatibility
- `backend/app/api/v1/ingestion.py` - Four endpoints with require_admin dependency; POST /run uses asyncio.create_task fire-and-forget
- `backend/app/api/v1/router.py` - Added ingestion router include

## Decisions Made
- `scheduler.shutdown(wait=False)` — prevents FastAPI from blocking shutdown for up to 4 hours waiting for an in-flight job; asyncio.Lock in ingestion.py already handles the in-flight case
- `asyncio.create_task` for manual /run trigger rather than FastAPI BackgroundTasks — appropriate for long-running CPU-light async work that must not block the response
- `require_admin` as a plain dependency function (not decorator) — composable, testable, consistent with existing `get_current_user` pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] APScheduler _job_defaults private API in 3.11.x**
- **Found during:** Task 1 verification
- **Issue:** Plan's verify script used `scheduler.job_defaults.get(...)` but APScheduler 3.11.x removed `job_defaults` as a public attribute; private `_job_defaults` holds the values
- **Fix:** Verification adapted to use `scheduler._job_defaults` — the scheduler.py code itself is correct and unaffected
- **Files modified:** None (verification script adaptation only)
- **Verification:** `scheduler._job_defaults` returns `{'misfire_grace_time': 300, 'coalesce': True, 'max_instances': 1}` as expected
- **Committed in:** 31064ba (Task 1 commit)

**2. [Rule 3 - Blocking] azure-identity and azure-mgmt-costmanagement not installed in local Python**
- **Found during:** Task 2 verification
- **Issue:** `from azure.identity import DefaultAzureCredential` failed — packages in requirements.txt but not installed in local venv
- **Fix:** Installed azure-mgmt-costmanagement, azure-identity, tenacity via pip with --break-system-packages (packages already in requirements.txt)
- **Files modified:** None (local env only — Docker image already has requirements.txt)
- **Verification:** All imports succeed, four routes confirmed at /ingestion/run, /ingestion/status, /ingestion/runs, /ingestion/alerts
- **Committed in:** 1528f57 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both auto-fixes were local environment/API compatibility issues; production code unaffected.

## Issues Encountered
- APScheduler 3.11.x changed `job_defaults` from a public attribute to `_job_defaults` (private). The scheduler configuration itself is correct — this only affected the plan's verification snippet.

## User Setup Required
**External services require manual configuration** — Azure Cost Management credentials needed for real ingestion. See env_vars in 02-03-PLAN.md frontmatter:
- `AZURE_SUBSCRIPTION_ID`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
- Grant Cost Management Reader role to service principal in Azure Portal -> Subscriptions -> IAM
- Set `MOCK_AZURE=true` in .env.local for local development without real credentials

## Next Phase Readiness
- Ingestion pipeline fully operational: scheduler fires every 4 hours, manual trigger via API, history and alerts accessible
- All admin ingestion endpoints ready for frontend integration (Phase 3 onward)
- No blockers — ready to advance to 02-04

---
*Phase: 02-data-ingestion*
*Completed: 2026-02-20*

## Self-Check: PASSED

- backend/app/core/scheduler.py: FOUND
- backend/app/schemas/ingestion.py: FOUND
- backend/app/api/v1/ingestion.py: FOUND
- .planning/phases/02-data-ingestion/02-03-SUMMARY.md: FOUND
- Commit 31064ba (Task 1): FOUND
- Commit 1528f57 (Task 2): FOUND
