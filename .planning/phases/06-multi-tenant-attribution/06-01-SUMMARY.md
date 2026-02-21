---
phase: 06-multi-tenant-attribution
plan: "01"
subsystem: attribution-schema
tags: [sqlalchemy, alembic, postgresql, models, migration]
dependency_graph:
  requires: []
  provides: [TenantProfile model, AllocationRule model, TenantAttribution model, attribution tables in DB]
  affects: [06-02, 06-03, 06-04, 06-05]
tech_stack:
  added: []
  patterns: [utcnow() defined locally per model file, UUID PK, Mapped[] typed columns, __table_args__ for constraints/indexes]
key_files:
  created:
    - backend/app/models/attribution.py
    - backend/migrations/versions/29e392128bad_add_attribution_tables.py
  modified:
    - backend/migrations/env.py
decisions:
  - "server_default='true' added on is_new Boolean in migration — follows Phase 4 precedent for boolean server_defaults"
  - "migrations/env.py only mounts backend/app in Docker — migrations/ must be docker cp'd into container for autogenerate and upgrade"
metrics:
  duration: "1 min"
  completed: "2026-02-21"
  tasks: 2
  files: 3
---

# Phase 6 Plan 01: Attribution Schema Migration Summary

Three SQLAlchemy 2.0 models and an Alembic migration creating `tenant_profiles`, `allocation_rules`, and `tenant_attributions` tables in PostgreSQL, providing the schema foundation for all Phase 6 attribution work.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create attribution.py SQLAlchemy models | 83e8ac1 | backend/app/models/attribution.py |
| 2 | Update Alembic env.py and generate + apply migration | 883ec3e | backend/migrations/env.py, backend/migrations/versions/29e392128bad_add_attribution_tables.py |

## What Was Built

### TenantProfile model
Tracks distinct `tenant_id` tag values from `BillingRecord.tag`. Includes `is_new` flag for "New" badge in UI, `acknowledged_at` timestamp, `display_name` for admin-set human-readable name, and `first_seen` date. Unique constraint on `tenant_id`.

### AllocationRule model
Defines how shared resource costs are split across tenants via three methods: `by_count`, `by_usage`, and `manual_pct`. `manual_pct` stores a `{tenant_id: pct}` JSON dict. Unique constraint on `priority` enforces first-rule-wins ordering.

### TenantAttribution model
Pre-computed monthly cost totals per tenant. Stores `total_cost`, `pct_of_total`, `mom_delta_usd` (None when no prior month data), `top_service_category`, `allocated_cost` (from rules), and `tagged_cost` (directly tagged). `tenant_id` may be `'UNALLOCATED'` sentinel for unmatched costs. Unique constraint on `(tenant_id, year, month)` with indexes on `(year, month)` and `tenant_id`.

### Migration
Alembic autogenerate detected all three tables. `server_default='true'` manually added to `is_new` Boolean column following Phase 4 precedent. Migration `29e392128bad` applied cleanly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker volume mount only covers backend/app, not backend/migrations**
- **Found during:** Task 2
- **Issue:** The container only mounts `backend/app` as `/code/app`. Changes to `backend/migrations/env.py` on the host were not visible inside the container, causing autogenerate to run without the attribution import.
- **Fix:** Used `docker cp` to copy updated `env.py` into container before running `alembic revision --autogenerate`. Also used `docker cp` to copy the generated migration file from container back to host, and `docker cp` again to update the migration after adding `server_default='true'` before applying.
- **Files modified:** backend/migrations/env.py
- **Commit:** 883ec3e

## Verification Results

1. `python -c "from app.models.attribution import TenantProfile, AllocationRule, TenantAttribution"` — PASSED
2. `migrations/env.py` contains `from app.models import attribution` — PASSED
3. Migration file `29e392128bad_add_attribution_tables.py` exists and references all three tables — PASSED
4. `\dt` in psql shows `tenant_profiles`, `allocation_rules`, `tenant_attributions` — PASSED

## Self-Check: PASSED

Files verified present:
- backend/app/models/attribution.py — FOUND
- backend/migrations/env.py (updated) — FOUND
- backend/migrations/versions/29e392128bad_add_attribution_tables.py — FOUND

Commits verified:
- 83e8ac1 feat(06-01): add TenantProfile, AllocationRule, TenantAttribution SQLAlchemy models — FOUND
- 883ec3e feat(06-01): update alembic env.py and apply attribution tables migration — FOUND
