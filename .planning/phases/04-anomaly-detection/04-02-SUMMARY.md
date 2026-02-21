---
phase: 04-anomaly-detection
plan: "02"
subsystem: api
tags: [sqlalchemy, fastapi, pydantic, postgresql, anomaly-detection, post-ingestion-hook, csv-export]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    plan: "01"
    provides: Anomaly SQLAlchemy model and anomalies PostgreSQL table (unique constraint on service_name, resource_group, detected_date)
  - phase: 02-data-ingestion
    provides: ingestion.py session management patterns, upsert pattern, _do_ingestion hook integration point
  - phase: 03-cost-monitoring
    provides: cost.py service layer conventions (async queries, func.sum/count, service-returns-rows/api-maps-to-pydantic), cost.py API router pattern (get_current_user dependency, StreamingResponse CSV export)
provides:
  - Anomaly detection service (backend/app/services/anomaly.py) with 8 functions: run_anomaly_detection, upsert_anomaly, auto_resolve_anomalies, get_anomalies, get_anomaly_summary, update_anomaly_status, mark_anomaly_expected, get_anomalies_for_export
  - Post-ingestion hook: run_anomaly_detection called from _do_ingestion after upsert_billing_records
  - Pydantic schemas (backend/app/schemas/anomaly.py): AnomalyResponse, AnomalySummaryResponse, AnomalyStatusUpdate, AnomalyMarkExpectedRequest
  - FastAPI anomaly router (backend/app/api/v1/anomaly.py) with 6 endpoints under /api/v1/anomalies
  - Anomaly router registered in api_router with prefix=/anomalies
affects: [04-03, 04-04, 04-05, anomaly-frontend, anomaly-ui-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Detection algorithm: 30-day rolling baseline via two-step SQLAlchemy subquery (daily_sub -> baseline_stmt) using func.avg over func.sum — same pattern as cost.py get_spend_summary
    - Anomaly upsert: pg_insert ON CONFLICT DO UPDATE with selective set_ dict — updates metric columns, preserves status/expected (same pattern as upsert_billing_records)
    - Post-ingestion hook: run_anomaly_detection(session) called after upsert_billing_records returns (which commits internally), before clear_active_alerts
    - Auto-resolve: query open anomalies for check_date, mark resolved if key not in still_active set; caller commits
    - Summary KPIs: individual select(func.count/sum) queries per metric (same style as cost.py get_spend_summary)
    - API router: APIRouter with tags only (prefix set at include_router level), get_current_user dependency on all endpoints
    - CSV export: io.StringIO + csv.writer + StreamingResponse(iter([output.getvalue()])) — same pattern as cost.py /export
    - Filter options endpoint: single GET /filter-options returns {services, resource_groups} dict — used for dropdown population

key-files:
  created:
    - backend/app/services/anomaly.py
    - backend/app/schemas/anomaly.py
    - backend/app/api/v1/anomaly.py
  modified:
    - backend/app/services/ingestion.py
    - backend/app/api/v1/router.py

key-decisions:
  - "check_date uses MAX(usage_date) from billing_records rather than today-1 — robust to Azure data latency (Research Open Question 2 resolved)"
  - "APIRouter prefix set at include_router level (not in APIRouter constructor) — follows existing cost.py pattern where router = APIRouter(prefix='/costs'); anomaly router uses tags-only constructor"
  - "GET /filter-options returns combined {services, resource_groups} dict instead of two separate /services and /resource-groups endpoints — simpler API surface, one round-trip for UI dropdowns (plan allowed Claude's discretion)"
  - "Detection accuracy denominator: total_detected = count of non-dismissed anomalies ever; expected_count = count where expected=True; returns None when total_detected=0 (same null pattern as mom_delta_pct)"

patterns-established:
  - "Post-ingestion hook pattern: detection service called with shared session after upsert commits; detection function commits its own changes; call order: upsert (commits) -> detection (commits) -> clear_alerts -> log_run"
  - "Anomaly lifecycle: status transitions enforced at API layer (validated against allowed set); expected flag + dismissed status combined in mark_expected endpoint"
  - "Service layer returns ORM objects; API layer maps with model_validate(row) — consistent with Phase 3 service-returns-rows/api-maps pattern"

requirements-completed: [ANOMALY-01, ANOMALY-02, ANOMALY-03]

# Metrics
duration: 6min
completed: 2026-02-21
---

# Phase 4 Plan 02: Anomaly Detection Backend Summary

**30-day rolling baseline detection service with post-ingestion hook, pg_insert upsert preserving user actions, 7-KPI summary, and 6 FastAPI endpoints including CSV export — all wired and live in OpenAPI**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-21T09:56:43Z
- **Completed:** 2026-02-21T10:02:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Created `backend/app/services/anomaly.py` with 8 functions implementing the full detection algorithm (30-day SQL subquery baseline, MAX(usage_date) as check_date, 20% + $100 thresholds, severity classification, upsert preserving status/expected, auto-resolve, CRUD helpers, export)
- Wired `run_anomaly_detection(session)` into `_do_ingestion()` in `ingestion.py` after `upsert_billing_records` — detection now runs automatically after every ingestion cycle
- Created `backend/app/schemas/anomaly.py` with all 4 Pydantic models and `backend/app/api/v1/anomaly.py` with 6 endpoints (list, summary, export, filter-options, status PATCH, expected PATCH); registered in router.py
- All 6 endpoints visible in OpenAPI at /api/v1/anomalies; API restarts without errors; all module imports verified clean inside running container

## Task Commits

Each task was committed atomically:

1. **Task 1: Anomaly detection service** - `3587ae2` (feat)
2. **Task 2: Wire post-ingestion hook, schemas, API router, register router** - `e2f1aa4` (feat)

**Plan metadata:** _(to be added in final commit)_

## Files Created/Modified

- `backend/app/services/anomaly.py` — 8-function detection service: run_anomaly_detection, upsert_anomaly, auto_resolve_anomalies, get_anomalies, get_anomaly_summary, update_anomaly_status, mark_anomaly_expected, get_anomalies_for_export
- `backend/app/schemas/anomaly.py` — AnomalyResponse (with model_config from_attributes), AnomalySummaryResponse, AnomalyStatusUpdate, AnomalyMarkExpectedRequest
- `backend/app/api/v1/anomaly.py` — FastAPI router with 6 endpoints: GET /, GET /summary, GET /export, GET /filter-options, PATCH /{id}/status, PATCH /{id}/expected
- `backend/app/services/ingestion.py` — Added import and call to run_anomaly_detection in _do_ingestion after upsert_billing_records
- `backend/app/api/v1/router.py` — Added anomaly router import and include_router with prefix=/anomalies

## Decisions Made

- `check_date` uses `SELECT MAX(usage_date) FROM billing_records` rather than `date.today() - 1` — robust to Azure data latency where yesterday's data may not yet exist in the billing table (resolves Research Open Question 2)
- `GET /filter-options` returns combined `{"services": [...], "resource_groups": [...]}` dict rather than two separate endpoints — one round-trip for UI dropdown population; plan allowed Claude's discretion for endpoints 6 and 7
- `APIRouter` constructed without prefix (tags-only); prefix `/anomalies` set at `include_router` call in router.py — follows same pattern used for cost router

## Deviations from Plan

None — plan executed exactly as written. The filter-options consolidated endpoint (vs two separate /services and /resource-groups endpoints) was explicitly allowed as Claude's discretion in the plan.

## Issues Encountered

None. All module imports verified clean inside running container before commit. `/api/docs` HTML verified returning 200; 6 anomaly routes confirmed in `/openapi.json`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Anomaly detection backend is fully operational: detection runs post-ingestion, writes to anomalies table, exposes CRUD API
- All 6 endpoints require JWT auth and are ready for frontend consumption
- Ready for Phase 4 Plan 03: Anomalies page frontend (AnomaliesPage.tsx with card-list UI, TanStack Query hooks, filter dropdowns, export button)
- Dashboard card integration (anomaly count card on DashboardPage) can proceed in parallel or as part of Plan 03

---
*Phase: 04-anomaly-detection*
*Completed: 2026-02-21*
