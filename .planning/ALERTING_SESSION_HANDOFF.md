# Alerting System — Session Handoff

**Date:** 2026-03-25
**Status:** Implementation complete, demo interrupted before finishing

---

## Session Summary

### Primary Request and Intent
- **Requirements gathering**: Consolidated alerting system requirements from CS701/ (authoritative/newer) and CS700/ (older, for gap analysis) into a single development-ready document. Output: `CS701/ALERTING_REQUIREMENTS.md`.
- **MVP implementation**: Implemented the full alerting system (budget management, anomaly alerting, notification delivery) in the existing `monroe_cloud_optimization` FastAPI codebase.
- **Three key decisions confirmed by user**: (1) Keep APScheduler (not switch to Celery), (2) Use generic SMTP for email, (3) Route anomaly/ingestion alerts to all active notification channels.
- **Demo**: Ran the system with seeded data and used Playwright to show what the alerting system looks like in action. This was interrupted and the user indicated something was "not implemented correctly" before asking for this summary.

### Key Technical Concepts
- FastAPI async backend (SQLAlchemy 2.0 async, asyncpg, PostgreSQL)
- APScheduler for scheduled jobs (not Celery)
- Alembic migrations
- Budget threshold alerting (check every 4h, fire once per billing period)
- Anomaly detection (30-day rolling baseline, existing service)
- Notification delivery: email (aiosmtplib + SMTP) and webhook (httpx + HMAC-SHA256 signing)
- Jinja2 HTML email templates
- Webhook retry job (every 15min, max 3 attempts, payload stored in `notification_deliveries.payload_json`)
- Role-based access control (admin/finance roles)
- Docker Compose dev environment

### Errors and Fixes Encountered
- **`recharts` not installed in frontend**: Fixed with `docker compose exec frontend npm install recharts`
- **`__init__.py` blocking model imports**: Fixed by adding all module imports to `app/models/__init__.py`
- **`utcnow` not defined in models**: Refactored `utcnow()` into `app.core.database`; all model files import from there
- **`require_admin` import path**: Moved to `app.core.dependencies` (was in `ingestion.py`)
- **`remove_threshold` signature**: Added optional `budget_id` parameter for ownership verification
- **Budget service session isolation**: Changed `check_budget_thresholds()` to open a separate `AsyncSessionLocal()` per budget
- **Swagger UI modal backdrop**: `backdrop-ux` div intercepted clicks; resolved by pressing Escape to dismiss

### Demo State at Interruption
- Stack: `db`, `redis`, `api`, `frontend` all up via Docker Compose
- Demo data seeded: 2 notification channels, 2 budgets, 4 thresholds
- Budget check manually triggered and confirmed working: 50% threshold fired ($1,068 of $2,000 = 53.4%), webhook delivered HTTP 200
- Playwright had navigated: login → dashboard → anomalies → Swagger API docs
- Was attempting to demonstrate live API calls in Swagger when user interrupted

### All User Messages (in order)
1. "help me gather all of the requirements for the alerting system to prepare it for development..."
2. "based on the existing code base, help me implement the mvp of the alerting system..."
3. "1. let's keep APScheduler / 2. use a generic SMTP / 3. go with option A"
4. "I don't want to install these things locally, can you just install them in the docker called monroe_cloud_optimization?"
5. "help me run it, i want an example of what it'll look like, maybe use playwright to help me record a video"
6. "it seems like it's not implemented correctly" *(interrupted Playwright demo — unclear if referring to video recording or the alerting system)*
7. "write a .md about the alerting work done during this session so that a new claude session can pick up from where we left off"

---

## What Was Built

A full budget alerting and notification delivery system was added to the existing FastAPI backend as an unplanned phase (slotted before Phase 7).

### New Files

| File | Purpose |
|------|---------|
| `backend/app/models/budget.py` | `Budget`, `BudgetThreshold`, `AlertEvent` ORM models |
| `backend/app/models/notification.py` | `NotificationChannel`, `NotificationDelivery` ORM models |
| `backend/app/schemas/budget.py` | Pydantic request/response schemas for all budget endpoints |
| `backend/app/schemas/notification.py` | Pydantic schemas for channels + deliveries (secret field redacted in responses) |
| `backend/app/services/budget.py` | Budget CRUD, `get_current_period_spend()`, `check_budget_thresholds()` scheduler job |
| `backend/app/services/notification.py` | Email (aiosmtplib) + webhook (httpx + HMAC-SHA256) delivery, retry job, broadcast helpers |
| `backend/app/api/v1/budget.py` | 9 REST endpoints (finance+admin gated) |
| `backend/app/api/v1/notification.py` | 4 REST endpoints (admin-only) |
| `backend/app/templates/email/budget_alert.html` | HTML email template for budget threshold alerts |
| `backend/app/templates/email/anomaly_detected.html` | HTML email template for anomaly alerts |
| `backend/app/templates/email/ingestion_failed.html` | HTML email template for ingestion failure alerts |
| `backend/migrations/versions/c8f1a9b3d2e4_add_budget_and_notification_tables.py` | Alembic migration (down_revision: `29e392128bad`) |

### Modified Files

| File | Change |
|------|--------|
| `backend/requirements.txt` | Added `aiosmtplib>=3.0`, `httpx>=0.27` |
| `backend/app/core/config.py` | Added SMTP settings block (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_START_TLS) |
| `backend/app/core/database.py` | Added `utcnow()` helper (imported by all models) |
| `backend/app/core/dependencies.py` | Added `require_admin` dependency (moved from ingestion.py) |
| `backend/app/models/__init__.py` | Added imports for `notification` and `budget` modules |
| `backend/migrations/env.py` | Added model imports for Alembic autogenerate |
| `backend/app/api/v1/router.py` | Registered `/budgets` and `/notifications` routers |
| `backend/app/main.py` | Added `check_budget_thresholds` (every 4h) and `retry_failed_deliveries` (every 15min) scheduler jobs |
| `backend/app/services/anomaly.py` | Added post-detection hook to call `notify_anomaly_detected()` for newly-detected anomalies |
| `backend/app/services/ingestion.py` | Added `notify_ingestion_failed()` call after `create_ingestion_alert()` |

---

## Key Decisions

1. **APScheduler (not Celery)** — kept existing scheduler, no broker/worker infrastructure needed
2. **Generic SMTP** — `aiosmtplib` with configurable SMTP_HOST; no provider lock-in
3. **Anomaly + ingestion alerts broadcast to all active channels** — no per-channel targeting for these; budget threshold alerts go to the one channel configured on the threshold
4. **Webhook retry via stored payload** — `notification_deliveries.payload_json` stores the full payload at first attempt; retry job reuses it (max 3 attempts, 15min interval)
5. **Budget threshold idempotency** — `last_triggered_period` on `BudgetThreshold` (format: `YYYY-MM` or `YYYY`) prevents double-firing within a billing period
6. **Anomaly deduplication** — snapshot existing open anomaly keys before detection run; dispatch only for newly-detected ones (set difference)
7. **Per-budget sub-sessions in `check_budget_thresholds()`** — one `AsyncSessionLocal()` per budget; failure of one budget doesn't roll back others

---

## API Surface

**Budget endpoints** (`/api/v1/budgets/`):
- `GET /` — list active budgets with current-period spend (all authenticated users)
- `POST /` — create budget (finance + admin)
- `GET /{id}` — budget detail + spend (all authenticated)
- `PUT /{id}` — update name/amount/end_date (finance + admin)
- `DELETE /{id}` — soft-delete, sets `is_active=False` (admin only)
- `POST /{id}/thresholds` — add threshold with optional notification channel (finance + admin)
- `GET /{id}/thresholds` — list thresholds (all authenticated)
- `DELETE /{id}/thresholds/{tid}` — remove threshold (admin only)
- `GET /{id}/alerts` — alert event history (all authenticated)

**Notification endpoints** (`/api/v1/notifications/`):
- `GET /channels` — list all channels (admin only)
- `POST /channels` — create email or webhook channel (admin only)
- `DELETE /channels/{id}` — delete channel (admin only)
- `GET /channels/{id}/deliveries` — last 100 delivery attempts (admin only)

---

## Database State

All 5 new tables are live (migration `c8f1a9b3d2e4` applied):
- `notification_channels`
- `notification_deliveries`
- `budgets`
- `budget_thresholds`
- `alert_events`

**Demo data seeded and verified:**
- 2 notification channels: `Ops Webhook` (webhook), `Finance Email` (email)
- 2 budgets: `Azure Subscription Budget` ($2,000/mo), `Production API Budget` ($400/mo, scope: `api-rg`)
- 4 thresholds: 50%, 75%, 90% on subscription budget; 90% on production API budget
- 1 alert event fired: 50% threshold on subscription budget triggered (spend was 53.4% = $1,068 of $2,000), webhook delivered HTTP 200, `last_triggered_period = 2026-03`

---

## What Was Left Unresolved

The user said **"it seems like it's not implemented correctly"** immediately before asking for this handoff document. It is **unclear what specifically is wrong.** Two possible interpretations:

1. The Playwright video recording approach — Playwright tracing produces `.zip` trace files, not `.mp4` video; the demo recording method may have been wrong
2. Something in the alerting implementation itself — a specific endpoint, the budget check logic, threshold firing, or notification delivery

**Next session should start by asking the user to clarify** what they meant before doing any further work.

---

## How to Run

```bash
cd /Users/wlfd/Developer/monroe_cloud_optimization
docker compose up -d
# API: http://localhost:8000/api/v1/health
# Swagger: http://localhost:8000/docs (or /api/docs)
# Frontend: http://localhost:5173
```

Manually trigger budget threshold check:
```bash
docker compose exec api python -c "
import asyncio
from app.services.budget import check_budget_thresholds
asyncio.run(check_budget_thresholds())
"
```

---

*Handoff written: 2026-03-25*
