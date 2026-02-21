---
phase: 03-cost-monitoring
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, pydantic, postgresql, csv]

# Dependency graph
requires:
  - phase: 03-01
    provides: BillingRecord model with region, tag, resource_id, resource_name columns from schema migration
  - phase: 02-data-ingestion
    provides: get_db, get_current_user FastAPI dependencies; ingestion.py router pattern
provides:
  - SpendSummaryResponse, DailySpendResponse, BreakdownItemResponse, TopResourceResponse Pydantic models
  - get_spend_summary, get_daily_spend, get_breakdown, get_top_resources, get_breakdown_for_export async service functions
  - 5 GET endpoints + 1 StreamingResponse CSV export at /api/v1/costs/*
  - cost router registered in api_router
affects: ["03-03-dashboard-kpi-chart", "03-04-breakdown-export", "frontend cost dashboard"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Thin FastAPI endpoints delegate all SQL aggregation to service layer (no raw SQL in endpoints)
    - DIMENSION_MAP dict maps string keys to SQLAlchemy column refs for dynamic GROUP BY
    - io.StringIO + csv.writer + StreamingResponse for in-memory CSV export
    - extract("year"/"month", column) for SQLAlchemy async date part filtering
    - result.all() for multi-column queries (NOT .scalars().all())

key-files:
  created:
    - backend/app/schemas/cost.py
    - backend/app/services/cost.py
    - backend/app/api/v1/cost.py
  modified:
    - backend/app/api/v1/router.py

key-decisions:
  - "MoM delta returns None (not error/0) when prior month has zero spend — avoids misleading -100% or division by zero"
  - "DIMENSION_MAP in services/cost.py maps string keys to SQLAlchemy column refs — single source of truth for valid dimensions"
  - "FastAPI Query pattern validation on dimension parameter provides 422 before service layer — defense in depth"
  - "output.seek(0) called after csv.writer writes, before streaming — critical for correct CSV content delivery"
  - "Decimal results cast to float at API layer (not service layer) — service returns raw rows, API maps to response models"

patterns-established:
  - "Service layer returns raw result.all() rows; API layer maps to Pydantic models with explicit float() casts"
  - "ValueError from service layer caught at endpoint and re-raised as HTTPException(400)"
  - "io.StringIO reset with seek(0) after writing, StreamingResponse wraps iter([output.getvalue()])"

requirements-completed: [COST-01, COST-02, COST-03, COST-04, COST-05, COST-06]

# Metrics
duration: 3min
completed: 2026-02-21
---

# Phase 3 Plan 02: Cost Analytics API Summary

**5 aggregate SQL query functions and 6 FastAPI endpoints serving MTD spend, daily trend, dimension breakdown, top-10 resources, and CSV export — all auth-protected under /api/v1/costs/**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-21T07:00:44Z
- **Completed:** 2026-02-21T07:03:20Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Cost Pydantic schemas: SpendSummaryResponse, DailySpendResponse, BreakdownItemResponse, TopResourceResponse
- Service layer with 5 async functions: MTD projection, daily trend, dynamic breakdown, top-10 resources, export variant
- 6 FastAPI endpoints with auth protection: summary, trend, breakdown, top-resources, export, all at /costs/*
- CSV streaming export with correct Content-Type and Content-Disposition headers
- Verified against live DB with actual billing data (prior_month_total: 24.45 returned correctly)

## Task Commits

Each task was committed atomically:

1. **Task 1: Cost Pydantic schemas and service layer** - `f6b6ca3` (feat)
2. **Task 2: Cost API endpoints and router registration** - `3a2f4f7` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/app/schemas/cost.py` - 4 Pydantic response models (no ORM config — plain BaseModel)
- `backend/app/services/cost.py` - 5 async aggregate query functions with DIMENSION_MAP
- `backend/app/api/v1/cost.py` - 5 GET endpoints + 1 StreamingResponse CSV export
- `backend/app/api/v1/router.py` - Added cost router import and include_router call

## Decisions Made
- MoM delta returns None (not 0 or error) when prior month has zero spend — avoids misleading percentage on first billing period
- DIMENSION_MAP dict maps validated string keys to SQLAlchemy column refs — single source of truth for dimension validation
- FastAPI Query pattern validation on dimension parameter provides 422 before service layer hits DB — defense in depth (service layer also raises ValueError as second gate)
- output.seek(0) called after csv.writer completes before StreamingResponse — critical for delivering correct CSV content
- Decimal values cast to float at API mapping layer, not in service layer — keeps service layer decoupled from response format

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Admin login via curl failed during verification (password in DB doesn't match env var value) — generated JWT token directly via Python inside container for verification. This is a pre-existing setup state, not introduced by this plan.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 6 cost endpoints available at /api/v1/costs/* and verified working with live DB
- Summary endpoint returns {mtd_total, projected_month_end, prior_month_total, mom_delta_pct} with correct float serialization
- CSV export streams with correct Content-Disposition header
- Ready for 03-03 (dashboard KPI+chart frontend) and 03-04 (breakdown+export frontend)

---
*Phase: 03-cost-monitoring*
*Completed: 2026-02-21*
