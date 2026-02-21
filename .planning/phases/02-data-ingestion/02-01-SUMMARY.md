---
phase: 02-data-ingestion
plan: "01"
subsystem: database
tags: [sqlalchemy, alembic, postgresql, azure, apscheduler, tenacity]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Base declarative class, async engine, migrations infrastructure, users table

provides:
  - BillingRecord SQLAlchemy model with composite unique constraint and 4 indexes
  - IngestionRun SQLAlchemy model tracking ingestion pipeline execution metadata
  - IngestionAlert SQLAlchemy model for persistent failure banners
  - Alembic migration 55bda49dc4a2 creating all three tables in PostgreSQL
  - Azure credential settings (AZURE_SUBSCRIPTION_ID, CLIENT_ID, TENANT_ID, CLIENT_SECRET, SUBSCRIPTION_SCOPE, MOCK_AZURE) in Settings
  - APScheduler, azure-mgmt-costmanagement, azure-identity, tenacity in requirements.txt

affects:
  - 02-02 (azure_client depends on AZURE_* settings and IngestionRun model)
  - 02-03 (ingestion service writes BillingRecord, IngestionRun, IngestionAlert)
  - 02-04 (scheduler reads IngestionRun status)
  - 02-05 (API endpoints read all three tables)

# Tech tracking
tech-stack:
  added:
    - APScheduler==3.11.2
    - azure-mgmt-costmanagement
    - azure-identity
    - tenacity
  patterns:
    - SQLAlchemy 2.0 mapped_column style following user.py pattern
    - utcnow() helper defined locally per model file (not shared import)
    - __table_args__ tuple with UniqueConstraint + Index objects
    - Azure credential settings as plain fields with empty string defaults (MOCK_AZURE bool for local dev)

key-files:
  created:
    - backend/app/models/billing.py
    - backend/migrations/versions/55bda49dc4a2_billing_ingestion_tables.py
  modified:
    - backend/app/core/config.py
    - backend/migrations/env.py
    - backend/requirements.txt

key-decisions:
  - "AZURE_SUBSCRIPTION_SCOPE stored as plain field with empty string default — ingestion service computes /subscriptions/{ID} at runtime from AZURE_SUBSCRIPTION_ID (simpler than model_validator)"
  - "MOCK_AZURE bool flag in Settings — allows local dev without real Azure credentials"
  - "utcnow() helper redefined in billing.py (not imported from user.py) — avoids coupling between model files"

patterns-established:
  - "SQLAlchemy 2.0 models: Mapped[type] annotations with mapped_column, __table_args__ tuple for constraints+indexes"
  - "Azure settings: AZURE_* prefix, all empty string defaults, MOCK_AZURE flag for development bypass"

requirements-completed:
  - INGEST-04
  - INGEST-05
  - INGEST-06

# Metrics
duration: 2min
completed: 2026-02-20
---

# Phase 2 Plan 01: Billing Database Models Summary

**Three SQLAlchemy billing models (BillingRecord, IngestionRun, IngestionAlert) with Alembic migration, composite unique constraint, Azure credential settings, and four new ingestion dependencies**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T00:53:52Z
- **Completed:** 2026-02-21T00:55:25Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- BillingRecord model with composite unique constraint on (usage_date, subscription_id, resource_group, service_name, meter_category) and 4 indexes for query performance
- IngestionRun model tracking pipeline execution metadata (status, triggered_by, window_start/end, retry_count, error_detail)
- IngestionAlert model for persistent failure banner state (is_active, cleared_at, cleared_by)
- Alembic migration 55bda49dc4a2 applies cleanly to PostgreSQL with all three tables and constraints verified
- Azure credential fields added to Settings with MOCK_AZURE flag for local development without real credentials

## Task Commits

Each task was committed atomically:

1. **Task 1: BillingRecord, IngestionRun, IngestionAlert models + Azure config settings** - `b8afe33` (feat)
2. **Task 2: Update migrations/env.py + generate Alembic migration for billing tables** - `acb4d78` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified

- `backend/app/models/billing.py` - Three SQLAlchemy 2.0 models with UniqueConstraint, indexes, utcnow helper
- `backend/migrations/versions/55bda49dc4a2_billing_ingestion_tables.py` - Alembic migration creating all three tables
- `backend/app/core/config.py` - Added AZURE_SUBSCRIPTION_ID, AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_SCOPE, MOCK_AZURE to Settings
- `backend/migrations/env.py` - Added `from app.models import billing` for autogenerate detection
- `backend/requirements.txt` - Added APScheduler==3.11.2, azure-mgmt-costmanagement, azure-identity, tenacity

## Decisions Made

- AZURE_SUBSCRIPTION_SCOPE as plain empty-string field — ingestion service computes `/subscriptions/{AZURE_SUBSCRIPTION_ID}` at runtime; avoids pydantic model_validator complexity
- utcnow() redefined in billing.py rather than imported from user.py — keeps model files decoupled
- MOCK_AZURE bool flag allows all downstream ingestion code to short-circuit Azure API calls for local development

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- System Python (homebrew) lacked asyncpg, causing `alembic revision --autogenerate` to fail with `sqlalchemy.dialects:driver` error. Resolved by passing `DATABASE_URL` environment variable explicitly (asyncpg was already installed at homebrew level; missing from PATH context). Migration ran cleanly once DATABASE_URL was set.

## User Setup Required

None — no external service configuration required beyond the existing .env.local pattern. Azure credentials (AZURE_SUBSCRIPTION_ID, AZURE_CLIENT_ID, AZURE_TENANT_ID, AZURE_CLIENT_SECRET) should be added to .env.local when real Azure integration begins in plan 02-02.

## Next Phase Readiness

- All three billing tables exist in PostgreSQL and are queryable
- BillingRecord, IngestionRun, IngestionAlert importable from `app.models.billing`
- Azure credential settings accessible via `settings.AZURE_SUBSCRIPTION_ID` etc.
- MOCK_AZURE=False by default (set True in .env.local for local dev without Azure)
- Ready for 02-02: AzureCostClient implementation using AZURE_* settings and IngestionRun model

---
*Phase: 02-data-ingestion*
*Completed: 2026-02-20*
