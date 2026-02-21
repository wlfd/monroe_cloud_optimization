---
phase: 06-multi-tenant-attribution
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, postgresql, attribution, multi-tenant, csv-export]

# Dependency graph
requires:
  - phase: 06-multi-tenant-attribution-01
    provides: TenantProfile, AllocationRule, TenantAttribution SQLAlchemy models and Alembic migration

provides:
  - Pydantic v2 schemas for attribution and settings (TenantAttributionResponse, AllocationRuleCreate with model_validator, etc.)
  - run_attribution() daily job: tenant discovery, allocation rule engine (by_count/by_usage/manual_pct), UNALLOCATED sentinel row, MoM delta, pg_insert upsert
  - GET /api/v1/attribution/ — pre-computed monthly totals per tenant
  - GET /api/v1/attribution/breakdown/{tenant_id} — per-service cost breakdown (on-the-fly from billing_records)
  - GET /api/v1/attribution/export — StreamingResponse CSV download
  - POST /api/v1/attribution/run — admin manual trigger (fire-and-forget asyncio.create_task)
  - 8 admin-only /settings endpoints for tenant profile management and allocation rule CRUD
  - Post-ingestion hook in ingestion.py that calls run_attribution() after anomaly detection
affects:
  - 06-multi-tenant-attribution-03 (frontend attribution page needs these endpoints)
  - 06-multi-tenant-attribution-04 (settings UI needs tenant/rule CRUD endpoints)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - _AttributionWithDisplayName wrapper class for two-step join without ORM relationship
    - apply_allocation_rule() pure function with by_count/by_usage/manual_pct dispatch
    - Post-ingestion hook pattern with non-fatal exception wrapping (same as anomaly detection)
    - fire-and-forget asyncio.create_task for POST /run admin endpoints

key-files:
  created:
    - backend/app/schemas/attribution.py
    - backend/app/services/attribution.py
    - backend/app/api/v1/attribution.py
    - backend/app/api/v1/settings.py
  modified:
    - backend/app/api/v1/router.py
    - backend/app/services/ingestion.py

key-decisions:
  - "_AttributionWithDisplayName wrapper class used for two-step join — TenantAttribution has no ORM relationship to TenantProfile; Python dict merge avoids JOIN complexity"
  - "apply_allocation_rule() is a pure function (not async) — takes cost + method + manual_pct + tenant_costs, returns dict; clean separation from DB layer"
  - "by_usage falls back to by_count when sum(tenant_costs) == 0 — prevents division-by-zero on first billing period before real usage data exists"
  - "UNALLOCATED row only written when unallocated > 0 — avoids phantom zero row cluttering attribution view"
  - "Post-ingestion attribution hook is non-fatal (try/except) — attribution failure does not fail the ingestion run record, same pattern as anomaly hook"
  - "run_attribution() opens its own AsyncSessionLocal session — runs outside request context (same pattern as anomaly detection and ingestion service)"

patterns-established:
  - "Pattern: Two-step ORM query + Python dict merge when no relationship defined between models"
  - "Pattern: Non-fatal post-ingestion hook with try/except logging for ancillary jobs"
  - "Pattern: fire-and-forget asyncio.create_task for long-running admin triggers"

requirements-completed: [ATTR-01, ATTR-02, ATTR-03, ATTR-04]

# Metrics
duration: 3min
completed: 2026-02-21
---

# Phase 6 Plan 02: Attribution Backend Summary

**FastAPI attribution engine with daily job (tenant discovery, allocation rules, UNALLOCATED sentinel), 4 attribution endpoints, 8 admin settings endpoints, and post-ingestion hook**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T21:27:43Z
- **Completed:** 2026-02-21T21:30:51Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Attribution service implementing full ATTR-01/ATTR-02 spec: tenant discovery via pg_insert upsert, tagged/untagged cost computation, allocation rule engine (by_count, by_usage, manual_pct), UNALLOCATED sentinel row, MoM delta, upsert via pg_insert ON CONFLICT
- REST API exposing attribution data: monthly totals list, per-service breakdown, CSV export, and admin manual trigger — satisfies ATTR-03 and ATTR-04
- 8 admin settings endpoints for tenant profile management (display names, acknowledge new) and allocation rule CRUD (list, create, update, delete, reorder priorities)
- Post-ingestion hook wired in ingestion.py after anomaly detection, non-fatal exception wrapping

## Task Commits

Each task was committed atomically:

1. **Task 1: Pydantic schemas and attribution service** - `58ccd74` (feat)
2. **Task 2: Attribution and Settings API routers + router registration + post-ingestion hook** - `d1063ae` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `backend/app/schemas/attribution.py` — Pydantic v2 schemas: TenantAttributionResponse, AllocationRuleCreate (with model_validator), AllocationRuleResponse, TenantProfileResponse, RuleReorderRequest, ServiceBreakdownItem, TenantDisplayNameUpdate, AllocationRuleUpdate
- `backend/app/services/attribution.py` — run_attribution() daily job, apply_allocation_rule() helper, get_attributions(), get_attribution_breakdown(), 8 CRUD functions for settings
- `backend/app/api/v1/attribution.py` — 4 endpoints under /attribution (list, breakdown, export CSV, POST /run admin)
- `backend/app/api/v1/settings.py` — 8 admin endpoints under /settings for tenant profiles and allocation rules
- `backend/app/api/v1/router.py` — registered attribution and settings routers with /attribution and /settings prefixes
- `backend/app/services/ingestion.py` — added run_attribution import and post-ingestion hook call after anomaly detection

## Decisions Made

- **_AttributionWithDisplayName wrapper:** TenantAttribution has no ORM relationship to TenantProfile. Used a thin Python wrapper class (with __slots__) for the two-step query + dict-merge enrichment pattern rather than adding an ORM relationship. Avoids schema changes.
- **apply_allocation_rule() pure function:** Separated allocation math from DB access for clean testability. Takes cost + method + manual_pct + tenant_costs dict, returns {tenant_id: float}.
- **by_usage fallback to by_count:** When sum of tenant tagged costs is zero (first billing period), by_usage would divide by zero. Falls back to by_count automatically.
- **Non-fatal post-ingestion hook:** Attribution failure wrapped in try/except so it does not propagate to fail the ingestion run record. Same pattern used for anomaly detection hook.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Local Python environment missing `redis` module caused `from app.api.v1 import router` to fail when importing the recommendation module. Confirmed pre-existing environment issue (not caused by this plan). Docker container import verified successfully as alternative. Attribution and settings module imports verified clean locally without the full router.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 4 attribution API endpoints registered and visible in OpenAPI spec
- All 8 settings endpoints registered and accessible to admin users
- Attribution service ready for Phase 6 Plan 03 (frontend attribution page) — `GET /api/v1/attribution/` and `GET /api/v1/attribution/export` endpoints are the primary data sources
- Settings endpoints ready for Phase 6 Plan 04 (settings UI)

---
*Phase: 06-multi-tenant-attribution*
*Completed: 2026-02-21*
