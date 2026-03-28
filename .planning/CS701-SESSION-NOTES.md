# CS 701 — CloudCost Project: Session Notes & Implementation Reference

*Generated: 2026-03-25*
*Covers: Revised scope review, gap analysis, feature plans, and implementation guide*

---

## Quick Reference

**Section 1–2** — Project snapshot and what's already done (phases 1–6, 29/33 v1 requirements).

**Section 3** — The three missing features with their requirement IDs:
- Audit logging (`AUDIT-01/02/03`) — Phase 7
- Budget alerting (`BUDG-01/04`) — v2, but in-scope per revised scope doc
- Webhook/email notifications (`NOTIF-01/02`) — v2, but in-scope per revised scope doc

**Section 4** — The anomalies vs. alerts distinction written out clearly.

**Section 5** — Full implementation plan per feature: models, service logic, endpoints, background job registration patterns, SQL queries, and the correct migration ordering (notifications → budgets → audit log).

**Section 6** — The "things that will bite you" list: APScheduler vs Celery, the `metadata_` column naming collision, BIGSERIAL vs UUID for audit PK, webhook secret encryption, soft-delete rules, and transaction coupling for audit entries.

**Sections 7–9** — Complete file checklists, new env vars, and the scope doc quote confirming all three features are in-scope.

---

## 1. Project Snapshot

| Field | Value |
|---|---|
| Project | Cloud Infrastructure Cost Optimization Platform ("CloudCost") |
| Sponsor | Fileread (seed-stage legal tech, ~$2.5M ARR, ~30 tenants) |
| Deadline | Late March / Early April 2026 |
| Codebase | `/Users/wlfd/Developer/monroe_cloud_optimization` |
| Design Docs | `/Users/wlfd/Documents/Monroe_THo/Special Projects in CS/CS701/` |
| Stack | FastAPI, React 19, PostgreSQL 15, Redis, SQLAlchemy 2.0 (asyncpg), APScheduler |
| Auth | PyJWT + pwdlib[argon2] (argon2 hashing) |
| Background Jobs | **APScheduler** (AsyncIOScheduler) — NOT Celery |
| AI | Anthropic Claude (primary) + Azure OpenAI (fallback), Redis cache 24h TTL |
| Deployment | Azure Container Apps (API) + Azure Static Web Apps (frontend) |

---

## 2. What's Built — Phases 1–6 ✅

All six phases are complete, clean, and verified end-to-end. Zero TODO/FIXME stubs.

| Phase | Feature | Status |
|---|---|---|
| 1 | Foundation (auth, JWT, DB, Redis, scheduler) | ✅ Complete |
| 2 | Azure billing ingestion pipeline (4h schedule, 24mo backfill, retry) | ✅ Complete |
| 3 | Cost monitoring dashboard (KPIs, trends, breakdown, top-10, CSV export) | ✅ Complete |
| 4 | Anomaly detection (30-day rolling baseline, severity scoring, status lifecycle) | ✅ Complete |
| 5 | AI recommendations (LLM, daily batch, Redis cache, confidence scoring) | ✅ Complete |
| 6 | Multi-tenant attribution (tag-based, allocation rules, per-tenant reports) | ✅ Complete |

**29 of 33 v1 requirements complete.**

---

## 3. What's Missing — The Gap

Cross-referencing the revised scope document against the codebase reveals **3 unimplemented features**.

### 3.1 Phase 7: Audit Logging (v1 requirements)

Requirements: `AUDIT-01`, `AUDIT-02`, `AUDIT-03`, and `API-01`

- Append-only audit log for all user actions and system events
- Fields: timestamp, actor, action type, entity type, entity ID, before/after state (JSON)
- Immutable at the DB layer — no UPDATE or DELETE permitted
- Queryable REST endpoint with filters

### 3.2 Budget Configuration & Threshold Alerting (v2 requirements)

Requirements: `BUDG-01` through `BUDG-04`

Listed as in-scope in the revised scope document (Section 5.1: "Budget configuration and threshold-based alerting system").

- Admin-configured budgets scoped to subscription / resource group / service / tag
- Multiple thresholds per budget (e.g., alert at 80% and 100%)
- Background job checks spend vs thresholds after each ingestion run
- Fires once per threshold per billing period (deduplication)

### 3.3 Webhook & Email Notifications (v2 requirements)

Requirements: `NOTIF-01`, `NOTIF-02`

Listed as in-scope in revised scope document (Section 5.1: "REST API with webhook/email notifications").

- Notification channels: email (SMTP / SendGrid) and webhook (HMAC-signed HTTP POST)
- Events: budget threshold crossed, anomaly detected (critical/high only), ingestion failed, recommendations ready
- Retry logic: 3 attempts per webhook (immediate → +1 min → +5 min)

---

## 4. Concept Clarification: Anomalies vs. Alerts

This is a common point of confusion — they overlap in the notification layer but are fundamentally different things.

| | Anomaly | Alert (Budget Threshold) |
|---|---|---|
| **Origin** | System-detected (statistical deviation) | User-configured rule |
| **Trigger** | Spend deviates from 30-day rolling baseline | Spend crosses a configured dollar/percent threshold |
| **Action** | Human triages (investigate / dismiss / mark expected) | Notification fires automatically |
| **Recurrence** | Every new deviation = new anomaly | Once per billing period per threshold |
| **Stored in** | `anomalies` table | `alert_events` table |
| **Example** | "VM costs were 600% above baseline" | "You've spent 80% of your $10,000 March budget" |

Both can trigger notifications, but anomalies *exist independently* of notifications — you can browse them without any notification setup. Budget alerts *only matter* because a human configured a threshold.

---

## 5. Implementation Plan

### 5.1 Migration Ordering (critical)

The three new features all require Alembic migrations. They must chain in this exact order because of a foreign key dependency:

```
29e392128bad (existing tail)
       ↓
[new] notification_channels + notification_deliveries tables
       ↓
[new] budgets + budget_thresholds + alert_events tables (FK → notification_channels)
       ↓
[new] audit_log table + immutability trigger
```

If budget migration runs before notification migration, the FK on `budget_thresholds.notification_channel_id` will fail.

### 5.2 Feature 1: Audit Logging

**New files:**
- `backend/app/models/audit.py` — `AuditLog` ORM model
- `backend/app/schemas/audit.py` — Pydantic response schemas
- `backend/app/services/audit_service.py` — `audit_log()` helper
- `backend/app/api/v1/audit.py` — REST endpoints
- `backend/migrations/versions/[rev]_add_audit_log.py`

**Model design:**
- Primary key: `BIGSERIAL` (sequential integer, not UUID) — guarantees total ordering, `ORDER BY id DESC` is a free primary key scan
- Separate `event_id UUID` column as the stable external-facing identifier
- `actor_type`: `'user' | 'system' | 'api_key'` (CHECK constraint)
- `before_state` / `after_state`: JSONB
- `metadata_` (maps to DB column `metadata` — underscore suffix avoids collision with SQLAlchemy's own `.metadata` class attribute)

**DB immutability (AUDIT-03):**
Use a PostgreSQL `BEFORE` trigger that raises `restrict_violation` — **not** `DO INSTEAD NOTHING` RULE.

Why: A RULE silently discards UPDATE/DELETE and returns success to the caller. A BEFORE trigger raises SQLSTATE `23001`, which surfaces as SQLAlchemy `IntegrityError` — giving the developer clear, immediate feedback that they've violated the contract. A silent discard hides bugs.

```sql
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only: % not permitted on row id=%',
        TG_OP, OLD.id
    USING ERRCODE = 'restrict_violation';
    RETURN NULL;
END;
$$;
```

**`audit_log()` helper — transaction coupling pattern:**
```python
async def audit_log(db, *, actor_type, actor_id, action_type, ...):
    entry = AuditLog(...)
    db.add(entry)
    # DO NOT commit here — caller's transaction commits both action + audit row atomically
```

Call `await db.flush()` before `audit_log()` if you need the new entity's ID. Call `await db.commit()` once at the end. This guarantees: if the action rolls back, the audit entry rolls back with it. No orphaned entries, no missing entries.

**Never log these fields in before/after state:**
- `user.password_hash`
- `cloud_account.encrypted_client_secret`
- `api_key.key_hash` (log `key_prefix` only)
- `notification_channel.config_json.secret`

**Endpoints:**
- `GET /api/v1/audit/logs` — paginated, filterable by: `from`, `to`, `actor_id`, `actor_type`, `action_type` (supports prefix: `budget.` returns all `budget.*` actions), `entity_type`, `entity_id`
- `GET /api/v1/audit/logs/export` — `?format=csv` (default) or `?format=json`, max 10,000 rows
- Admin role only

**Required indexes in migration (don't forget):**
```sql
CREATE INDEX idx_audit_log_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_log_actor ON audit_log (actor_type, actor_id);
CREATE INDEX idx_audit_log_action_type ON audit_log (action_type);
CREATE INDEX idx_audit_log_entity ON audit_log (entity_type, entity_id);
```

**Actions to log:**

| Endpoint | Action Type |
|---|---|
| POST /auth/login (success) | `user.login` |
| POST /auth/login (failed) | `user.login_failed` |
| POST /auth/logout | `user.logout` |
| PATCH /anomalies/{id}/status | `anomaly.status_updated` |
| PATCH /recommendations/{id}/action | `recommendation.actioned` |
| POST /budgets | `budget.created` |
| PUT /budgets/{id} | `budget.updated` |
| DELETE /budgets/{id} | `budget.deactivated` |
| POST/DELETE /settings/tenants | `tenant.created` / `tenant.updated` |
| POST/DELETE /settings/allocation-rules | `allocation_rule.created` / `allocation_rule.updated` |
| POST /admin/notification-channels | `notification_channel.created` |
| POST /ingestion/run (manual trigger) | `ingestion.triggered_manual` |
| Ingestion job completes | `ingestion.completed` (actor_type: `system`) |
| Ingestion job fails | `ingestion.failed` (actor_type: `system`) |
| Anomaly detection job runs | `anomaly.detection_run_completed` (actor_type: `system`) |
| Recommendations batch runs | `recommendation.generation_completed` (actor_type: `system`) |

---

### 5.3 Feature 2: Budget Configuration & Threshold Alerting

**New files:**
- `backend/app/models/budget.py` — `Budget`, `BudgetThreshold`, `AlertEvent` models
- `backend/app/schemas/budget.py` — Pydantic schemas
- `backend/app/services/budget.py` — spend calculation + threshold checking
- `backend/app/api/v1/budget.py` — CRUD endpoints
- `backend/migrations/versions/[rev]_add_budget_tables.py`

**Model design:**

`Budget`:
- `scope_type`: `'subscription' | 'resource_group' | 'service' | 'tag'` (CHECK constraint)
- `scope_value`: nullable — `NULL` is valid when `scope_type = 'subscription'`
- `period`: `'monthly' | 'annual'` — **NOT weekly** (weekly was never in scope)
- `amount_usd`: NUMERIC(12,2)
- `is_active`: soft-delete only — never hard-delete budgets (alert history must remain)

`BudgetThreshold`:
- `threshold_percent`: INTEGER (e.g., 80, 100)
- `notification_channel_id`: UUID FK → `notification_channels.id` (nullable)
- `last_triggered_period`: VARCHAR(7) (e.g., `'2026-03'`) — prevents re-firing same period
- `last_triggered_at`: TIMESTAMP WITH TIME ZONE

`AlertEvent`:
- Records each threshold crossing: `budget_id`, `threshold_id`, `billing_period`, `spend_at_trigger`, `budget_amount`, `threshold_percent`, `delivery_status`

**Spend calculation query (for `check_budget_thresholds` job):**
```python
# scope_type=subscription: SUM all cost_usd for the account this period
# scope_type=resource_group: WHERE resource_group = scope_value
# scope_type=service: WHERE service_name = scope_value
# scope_type=tag: WHERE tags JSONB @> '{"key": "value"}' (parse scope_value as "key=value")
SELECT SUM(cost_usd)
FROM billing_records
WHERE DATE_TRUNC('month', date) = DATE_TRUNC('month', NOW())
  AND [scope filter]
```

**Background job registration (APScheduler pattern):**
```python
scheduler.add_job(
    check_budget_thresholds,
    trigger="cron",
    hour="1,5,9,13,17,21",    # 6x/day — shortly after ingestion windows
    minute=30,
    id="check_budget_thresholds",
    replace_existing=True,
)
```

**Endpoints:**
- `GET /api/v1/budgets` — list all budgets with current period spend
- `POST /api/v1/budgets` — create budget
- `GET /api/v1/budgets/{id}` — budget detail + threshold list + alert history
- `PUT /api/v1/budgets/{id}` — update budget
- `DELETE /api/v1/budgets/{id}` — soft-delete (`is_active = false`)
- `POST /api/v1/budgets/{id}/thresholds` — add threshold
- `DELETE /api/v1/budgets/{id}/thresholds/{threshold_id}` — remove threshold

**Pydantic validation note:** Use a `@model_validator` to enforce: when `scope_type == 'subscription'`, `scope_value` is not required. When `scope_type` is anything else, `scope_value` is required.

---

### 5.4 Feature 3: Webhook & Email Notifications

**New files:**
- `backend/app/models/notification.py` — `NotificationChannel`, `NotificationDelivery`
- `backend/app/schemas/notification.py` — discriminated union schemas
- `backend/app/services/notification_service.py` — `NotificationService` class
- `backend/app/templates/email/` — Jinja2 HTML templates (5 templates)
- `backend/migrations/versions/[rev]_add_notification_tables.py`

**Model design:**

`NotificationChannel`:
- `channel_type`: `'email' | 'webhook'` (CHECK constraint)
- `config_json`: JSONB
  - email: `{"address": "ops@fileread.com"}`
  - webhook: `{"url": "https://...", "secret": "<encrypted_hex>"}` — **secret must be AES-256 encrypted at rest** using the same encryption helper already used for Azure credentials
- `is_active`: soft-delete — use `is_active = false`, never hard-delete (delivery history references channel)

`NotificationDelivery`:
- Tracks every send attempt: `channel_id`, `event_type`, `event_id`, `attempt_number`, `status` (`pending | delivered | failed`), `response_code`, `error_message`
- Add `payload_json JSONB` column — stores the full payload at send time so the retry job can re-send without re-fetching the triggering entity

**Event types (use dot-notation strings, not underscore names):**
```python
class EventType(StrEnum):
    BUDGET_THRESHOLD_CROSSED = "budget.threshold_crossed"
    ANOMALY_DETECTED         = "anomaly.detected"
    INGESTION_FAILED         = "ingestion.failed"
    RECOMMENDATION_READY     = "recommendation.ready"
    API_KEY_EXPIRING         = "api_key.expiring"
```

**Standard webhook envelope:**
```json
{
  "event_type": "budget.threshold_crossed",
  "event_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "timestamp": "2026-03-25T14:30:00.000000+00:00",
  "data": { ... }
}
```

**HMAC signing:**
```python
body = json.dumps(envelope, default=str).encode("utf-8")
signature = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
# Header: X-CloudCost-Signature: sha256=<hex>
```

**Email delivery:** Use `aiosmtplib` for async SMTP. Config vars needed in `config.py`:
```
SMTP_HOST, SMTP_PORT (587), SMTP_USERNAME, SMTP_PASSWORD
SMTP_FROM_ADDRESS, SMTP_FROM_NAME
SMTP_USE_TLS (True — STARTTLS)
SENDGRID_API_KEY (optional — takes precedence over SMTP if set)
```

**Notification routing rules:**
- **Budget alerts**: route to `budget_threshold.notification_channel_id` (explicit per-threshold channel)
- **Anomaly alerts**: fan-out to all active channels (severity `critical` or `high` only; `medium` is dashboard-only)
- **Ingestion failures**: fan-out to all active channels
- **Recommendations ready**: fan-out to all active channels

**Retry job (APScheduler):**
```python
scheduler.add_job(
    retry_failed_webhooks,
    trigger="interval",
    minutes=15,
    id="retry_failed_webhooks",
    replace_existing=True,
)
```

Retry logic: max 3 total attempts. Attempt 1 = immediate. Attempt 2 = +1 min. Attempt 3 = +5 min. Email failures are **not** retried (SMTP failures are typically permanent). Only webhooks retry.

**Email templates needed** (Jinja2 HTML, in `backend/app/templates/email/`):
- `base.html` — shared layout
- `budget_alert.html` — vars: `budget_name`, `threshold_percent`, `spend_at_trigger`, `budget_amount`, `billing_period`
- `anomaly_detected.html` — vars: `service_name`, `severity`, `estimated_monthly_impact_usd`, `deviation_percent`, `resource_group`
- `ingestion_failed.html` — vars: `account_name`, `error_message`, `retry_count`
- `recommendation_ready.html` — vars: `recommendation_count`, `total_estimated_savings_usd`, `top_category`

**Endpoints:**
- `GET /api/v1/admin/notification-channels`
- `POST /api/v1/admin/notification-channels`
- `DELETE /api/v1/admin/notification-channels/{id}` — soft-delete only

**Pydantic schema:** Use a discriminated union on `channel_type` to enforce correct `config_json` structure at the API layer. Don't let malformed channels reach the DB.

---

## 6. Key Architecture Facts (Things That Will Bite You)

### APScheduler, NOT Celery
The design documents in the CS701 folder reference Celery. **The actual codebase uses APScheduler.** All background jobs use `scheduler.add_job()` registered during FastAPI lifespan startup. There is no `app/tasks/` folder with Celery task files. Register new jobs in `core/scheduler.py`.

### `metadata_` column name
SQLAlchemy's `DeclarativeBase` subclasses have a `.metadata` class attribute (the `MetaData` object). If you name an ORM column `metadata`, you'll get a collision. Map it as:
```python
metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=True)
```

### BIGSERIAL vs UUID for audit log
The audit log PK is `BIGSERIAL` (sequential integer), not UUID. This is intentional — `ORDER BY id DESC` is a free primary key index scan, which is the default query pattern for the audit log. The externally-exposed identifier is `event_id UUID`.

### Webhook secret encryption
Webhook secrets stored in `config_json.secret` must be AES-256 encrypted. The project already has an encryption helper for Azure credentials. Reuse it — don't store secrets in plaintext JSONB.

### Soft-delete everywhere
- Budgets: set `is_active = false`
- Notification channels: set `is_active = false`
- Never hard-delete entities that have child records (alert history, delivery history)

### Transaction coupling for audit logs
The `audit_log()` helper must **not** call `db.commit()`. It adds the entry to the current open session. The endpoint commits once at the end, covering both the business action and the audit entry atomically. A failed rollback removes both. This is the correct pattern.

---

## 7. Files to Create / Modify (Summary)

### New model files
- `backend/app/models/notification.py`
- `backend/app/models/budget.py`
- `backend/app/models/audit.py`

### New schema files
- `backend/app/schemas/notification.py`
- `backend/app/schemas/budget.py`
- `backend/app/schemas/audit.py`

### New service files
- `backend/app/services/notification_service.py`
- `backend/app/services/budget.py`
- `backend/app/services/audit_service.py`

### New API endpoint files
- `backend/app/api/v1/notification.py`
- `backend/app/api/v1/budget.py`
- `backend/app/api/v1/audit.py`

### New Alembic migrations (in order)
1. `[rev1]_add_notification_tables.py`
2. `[rev2]_add_budget_tables.py` (depends on rev1)
3. `[rev3]_add_audit_log.py` (depends on rev2)

### Files to modify
- `backend/app/api/v1/router.py` — include 3 new routers
- `backend/app/core/scheduler.py` — register `check_budget_thresholds` and `retry_failed_webhooks` jobs
- `backend/app/core/config.py` — add SMTP/SendGrid env vars
- `backend/app/services/anomaly.py` — call `dispatch_event(ANOMALY_DETECTED)` on critical/high anomalies
- `backend/app/services/ingestion.py` — call `dispatch_event(INGESTION_FAILED)` on final failure
- `backend/app/services/recommendation.py` — call `dispatch_event(RECOMMENDATION_READY)` after daily batch
- `backend/app/api/v1/auth.py` — add `audit_log()` for login/logout
- `backend/app/api/v1/anomaly.py` — add `audit_log()` for status updates
- `backend/app/api/v1/recommendation.py` — add `audit_log()` for action updates
- `backend/app/api/v1/settings.py` — add `audit_log()` for tenant/allocation rule mutations

### New template files
- `backend/app/templates/email/base.html`
- `backend/app/templates/email/budget_alert.html`
- `backend/app/templates/email/anomaly_detected.html`
- `backend/app/templates/email/ingestion_failed.html`
- `backend/app/templates/email/recommendation_ready.html`

---

## 8. Environment Variables to Add

```bash
# Email / notifications
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=               # SendGrid password or app password
SMTP_FROM_ADDRESS=cloudcost@fileread.com
SMTP_FROM_NAME=CloudCost
SMTP_USE_TLS=true
SENDGRID_API_KEY=            # Optional — if set, used instead of raw SMTP
WEBHOOK_TIMEOUT_SECONDS=10
WEBHOOK_MAX_RETRIES=3
```

---

## 9. Scope Document Reference (Section 5.1)

The revised scope document explicitly includes these as **in-scope implementation deliverables**:

> - Azure Cost Management API integration ✅
> - Real-time cost monitoring dashboard ✅
> - **Budget configuration and threshold-based alerting system** ← Feature 2
> - AI-powered cost forecasting and recommendations ✅
> - Rule-based anomaly detection ✅
> - Tag-based multi-tenant cost attribution ✅
> - Per-tenant cost views and reporting ✅
> - **Basic audit logging for platform actions** ← Feature 1
> - **REST API with webhook/email notifications** ← Feature 3

---

*Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization`*
*Design docs: `/Users/wlfd/Documents/Monroe_THo/Special Projects in CS/CS701/`*
*Planning: `/Users/wlfd/Developer/monroe_cloud_optimization/.planning/`*
