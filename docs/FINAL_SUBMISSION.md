# CloudCost — CS 701 Final Documentation Submission

**Course:** CS 701 — Special Projects in Computer Science II  
**Project Title:** Cloud Infrastructure Cost Optimization Platform  
**Student:** Tsun Shan Ho  
**Sponsor:** Fileread  
**Date:** April 2026  
**Professor:** Dr. Samson Ogola

---

> **Submission Instructions — Image Files**
> The diagram screenshots below reference the PNG files you exported from draw.io. Before converting this document to PDF or Word, copy the following four files into the same folder as this document (`docs/`):
>
> | Filename | Source |
> |----------|--------|
> | `DFD-Level 0 - Context.drawio.png` | Exported from `docs/DFD.drawio`, Page 1 |
> | `DFD-Level 1 - DFD.drawio (1).png` | Exported from `docs/DFD.drawio`, Page 2 |
> | `ERD_FULL.drawio.png` | Exported from `docs/ERD_FULL.drawio` |
> | `NETWORK-Prod - Azure Architecture.drawio (2).png` | Exported from `docs/NETWORK.drawio`, Page 2 |
>
> *Note: The development network diagram (Page 1 of `NETWORK.drawio`, showing Docker Compose topology) was not exported. If you want to include it, export it from app.diagrams.net and reference it in Section 5.3.*

---

## Table of Contents

1. [Completed Code](#1-completed-code)
2. [E-R Diagram](#2-e-r-diagram)
3. [Project Scoping Document](#3-project-scoping-document)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [Network Diagram](#5-network-diagram)
6. [Security Measures](#6-security-measures)

---

## 1. Completed Code

### 1.1 Platform Overview

CloudCost is a SaaS platform that automates Azure cloud cost management for Fileread. The system ingests billing data from the Azure Cost Management API every four hours, detects statistical cost anomalies, generates AI-powered optimization recommendations via Anthropic Claude, attributes costs to approximately 30 internal tenants using tag-based rules, and sends threshold-based budget alerts via email and webhook.

The technology stack is:

| Layer | Technology |
|-------|------------|
| Backend API | FastAPI (Python 3.12) with async SQLAlchemy 2.0 |
| Frontend | React 19 / TypeScript with TanStack Query and shadcn/ui |
| Database | PostgreSQL 15 (16 tables, async driver via asyncpg) |
| Cache | Redis 7 (recommendation cache + LLM call counter) |
| Scheduler | APScheduler (in-process, 4 background jobs) |
| AI | Anthropic Claude Sonnet 4.6 (primary) + Azure OpenAI (fallback) |
| Containerization | Docker Compose (development), Azure Container Apps (production) |

### 1.2 Backend Architecture

The backend follows a strict three-layer pattern:

```
backend/app/
├── api/v1/          ← FastAPI route handlers (HTTP boundary)
│   ├── auth.py
│   ├── cost.py
│   ├── anomaly.py
│   ├── recommendation.py
│   ├── attribution.py
│   ├── budget.py
│   ├── notification.py
│   ├── ingestion.py
│   └── settings.py
├── schemas/         ← Pydantic request/response models
├── services/        ← Business logic (all async, accept AsyncSession)
│   ├── ingestion.py
│   ├── anomaly.py
│   ├── recommendation.py
│   ├── attribution.py
│   ├── budget.py
│   ├── notification.py
│   ├── cost.py
│   └── azure_client.py
└── models/          ← SQLAlchemy ORM models
    ├── user.py
    ├── billing.py
    ├── recommendation.py
    ├── attribution.py
    └── budget.py
```

Every route handler accepts database sessions via `Depends(get_db)` and the authenticated user via `Depends(get_current_user)`. Business logic lives entirely in the services layer — route handlers only parse requests, call services, and return schemas. This separation keeps each layer independently testable.

### 1.3 Code Snapshots

#### Authentication — Login Endpoint (`backend/app/api/v1/auth.py`)

The login endpoint demonstrates the authentication flow: credential verification, brute-force lockout enforcement, JWT token issuance, and HttpOnly refresh-token cookie writing.

```python
@router.post("/login", response_model=TokenResponse)
async def login(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    # Look up user by email
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Check brute-force lockout before attempting password verification
    if user.locked_until is not None and user.locked_until > datetime.now(UTC):
        raise HTTPException(status_code=429, detail="Account temporarily locked")

    if not verify_password(form_data.password, user.password_hash):
        # Increment failed attempt counter; lock account after 5 failures
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= 5:
            user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Successful login: reset lockout counters
    user.failed_login_attempts = 0
    user.locked_until = None

    # Issue short-lived access token (60 min, in-memory) + long-lived refresh token (7 days)
    access_token = create_access_token({"sub": str(user.id), "role": user.role})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Store hashed refresh token in user_sessions table (not the raw token)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh_token),
        expires_at=datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(session)
    await db.commit()

    # Set HttpOnly cookie — inaccessible to JavaScript
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )
    return TokenResponse(access_token=access_token, token_type="bearer")
```

**Design decisions:**
- The lockout check occurs *before* password verification to avoid unnecessary Argon2 computation on locked accounts.
- Only the SHA-256 hash of the refresh token is stored in the database — the raw token is never persisted.
- The access token is returned in the JSON response body (stored in memory by the frontend) while the refresh token is set in an HttpOnly cookie that cannot be accessed by JavaScript.

---

#### Billing Ingestion Pipeline — Idempotent Upsert (`backend/app/services/ingestion.py`)

The ingestion service computes an incremental delta window and upserts records idempotently using PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE`.

```python
async def compute_delta_window(session: AsyncSession) -> tuple[datetime, datetime]:
    """Calculate the (start, end) window for the next incremental fetch.

    A 24-hour overlap is applied to the start date to catch late-arriving Azure
    records. The window is capped at 7 days to avoid overwhelming the API after
    an extended outage.
    """
    now = datetime.now(UTC)
    last_run = await get_last_successful_run(session)

    if last_run is None or last_run.window_end is None:
        # First scheduled run — use a small 4-hour window; backfill covers history.
        return now - timedelta(hours=4), now

    raw_start = last_run.window_end - timedelta(hours=24)   # 24-hour overlap
    cap_start = now - timedelta(days=7)                      # 7-day cap
    start = max(raw_start, cap_start)
    return start, now


async def upsert_billing_records(session: AsyncSession, records: list[dict]) -> int:
    """Idempotently insert or update billing records.

    Conflict target: (usage_date, subscription_id, resource_group,
                      service_name, meter_category)
    On conflict: update pre_tax_cost, currency, updated_at only.
    """
    rows = [_map_record(r) for r in records]

    stmt = pg_insert(BillingRecord).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[
            "usage_date", "subscription_id", "resource_group",
            "service_name", "meter_category",
        ],
        set_={
            "pre_tax_cost": stmt.excluded.pre_tax_cost,
            "currency":     stmt.excluded.currency,
            "updated_at":   stmt.excluded.updated_at,
        },
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

**Design decisions:**
- The 24-hour overlap window catches billing records that Azure publishes late (Azure Cost Management API can publish records 12–24 hours after the billing day closes).
- The 7-day cap prevents a catch-up storm after a prolonged outage.
- `ON CONFLICT DO UPDATE` makes the upsert idempotent — re-running the ingestion against the same date range produces no duplicate rows and updates only the cost value if it changed.

---

#### Anomaly Detection Algorithm (`backend/app/services/anomaly.py`)

The anomaly detector runs as a post-ingestion hook and implements a 30-day rolling baseline.

```python
async def run_anomaly_detection(session: AsyncSession) -> None:
    """30-day rolling baseline anomaly detection.

    Algorithm:
    1. Compute baseline: average daily cost per (service_name, resource_group)
       over the past 30 days.
    2. Find the most recent completed billing day.
    3. Fetch current day's spend per (service_name, resource_group).
    4. Flag pairs where pct_deviation >= 20% AND monthly_impact >= $100.
    5. Severity: critical (>= $1000/mo), high (>= $500), medium (>= $100).
    6. Upsert detected anomalies; auto-resolve those that no longer trigger.
    """
    baseline_cutoff = date.today() - timedelta(days=30)

    # Step 1: Compute daily cost subtotals over the 30-day baseline window
    daily_sub = (
        select(
            BillingRecord.service_name,
            BillingRecord.resource_group,
            BillingRecord.usage_date,
            func.sum(BillingRecord.pre_tax_cost).label("daily_cost"),
        )
        .where(BillingRecord.usage_date >= baseline_cutoff)
        .group_by(
            BillingRecord.service_name,
            BillingRecord.resource_group,
            BillingRecord.usage_date,
        )
        .subquery()
    )

    # Step 2: Average those daily subtotals to get the baseline per (service, resource_group)
    baseline_stmt = select(
        daily_sub.c.service_name,
        daily_sub.c.resource_group,
        func.avg(daily_sub.c.daily_cost).label("baseline_avg_daily"),
    ).group_by(daily_sub.c.service_name, daily_sub.c.resource_group)

    baseline_rows = (await session.execute(baseline_stmt)).all()

    if not baseline_rows:
        logger.warning("No 30-day baseline data — skipping detection")
        return

    # Step 3: Find the most recent completed billing day
    max_date_stmt = select(func.max(BillingRecord.usage_date))
    check_date = (await session.execute(max_date_stmt)).scalar()

    # (Steps 4–6 continue: current-day spend comparison, upsert, auto-resolve)
```

**Design decisions:**
- Using a two-level subquery (daily subtotals → average) ensures the baseline is computed per billing day rather than per billing record, producing a true average daily spend.
- Both a percentage threshold (20%) and an absolute dollar threshold ($100/month estimated impact) are required together to filter out noise from very small or very large services.
- Auto-resolve: any previously open anomaly that no longer exceeds both thresholds is automatically moved to `resolved` status so the anomaly list does not become stale.

---

#### AI Recommendation Pipeline — LLM Tool Call (`backend/app/services/recommendation.py`)

The recommendation service calls Anthropic Claude with a forced-structure tool definition to produce machine-readable JSON output, then falls back to Azure OpenAI on failure.

```python
# Forced-output tool definition — Claude must call this tool with structured fields
RECOMMENDATION_TOOL = {
    "name": "record_recommendation",
    "input_schema": {
        "type": "object",
        "properties": {
            "category":                  {"type": "string",
                                          "enum": ["right-sizing", "idle", "reserved", "storage"]},
            "explanation":               {"type": "string"},
            "estimated_monthly_savings": {"type": "number"},
            "confidence_score":          {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["category", "explanation", "estimated_monthly_savings", "confidence_score"],
    },
}


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (anthropic.RateLimitError, anthropic.InternalServerError, anthropic.APIConnectionError)
    ),
)
async def _call_anthropic(client: anthropic.AsyncAnthropic, resource: dict) -> dict:
    """Call Anthropic Claude Sonnet 4.6 with tool_choice=required for structured output."""
    response = await client.messages.create(
        model=get_settings().ANTHROPIC_MODEL,
        max_tokens=512,
        tools=[RECOMMENDATION_TOOL],
        tool_choice={"type": "tool", "name": "record_recommendation"},
        messages=[{"role": "user", "content": _build_prompt(resource)}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_recommendation":
            return block.input
    raise ValueError("No tool_use block in response")


async def _generate_for_resource(resource, anthropic_client, redis_client, limit) -> dict | None:
    """Check Redis cache → check daily limit → call LLM → fallback to Azure OpenAI."""
    cache_key = _make_cache_key(
        resource["subscription_id"], resource["resource_group"], resource["resource_name"]
    )

    # 1. Cache hit: return stored result without counting against daily limit
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. Daily call limit check (Redis INCR — atomic increment)
    allowed = await _check_and_increment_counter(redis_client, limit)
    if not allowed:
        return None                   # Limit exceeded for today; skip

    # 3. Primary: Anthropic Claude with retry
    try:
        result = await _call_anthropic(anthropic_client, resource)
    except Exception as exc:
        logger.warning("Anthropic failed after 3 retries: %s — trying Azure OpenAI", exc)
        result = await _call_azure_openai(resource)   # 4. Fallback

    if result:
        # Store in Redis for 24 hours to avoid duplicate calls
        await redis_client.set(cache_key, json.dumps(result), ex=86400)

    return result
```

**Design decisions:**
- `tool_choice={"type": "tool", "name": "record_recommendation"}` forces Claude to always call the tool — this prevents the model from returning a freeform text response that would require additional parsing.
- The Redis cache key includes the resource identity and today's date, so stale cached results expire automatically at the 24-hour TTL boundary.
- The daily call counter uses Redis `INCR` with an `EXPIREAT` set to midnight UTC, making the counter atomically thread-safe without a separate lock.

### 1.4 Frontend Architecture

The frontend is a React 19 single-page application using TypeScript throughout:

```
frontend/src/
├── pages/           ← Route-level components (one per page)
│   ├── LoginPage.tsx
│   ├── DashboardPage.tsx
│   ├── AnomaliesPage.tsx
│   ├── RecommendationsPage.tsx
│   ├── AttributionPage.tsx
│   ├── IngestionPage.tsx
│   ├── SettingsPage.tsx
│   └── NotFoundPage.tsx
├── services/        ← TanStack Query hooks + Axios API client
│   ├── api.ts       ← Axios instance with JWT injection + 401 refresh interceptor
│   ├── cost.ts
│   ├── anomaly.ts
│   └── recommendation.ts
├── hooks/
│   └── useAuth.tsx  ← Auth context (in-memory token, session restore)
└── components/      ← shadcn/ui primitive wrappers
```

Data fetching uses TanStack Query (`useQuery` for reads, `useMutation` for writes). The Axios instance in `services/api.ts` includes a response interceptor that automatically refreshes the access token on any 401 response and replays the original request — the calling component never needs to handle token expiry explicitly.

### 1.5 Database Schema

The PostgreSQL database contains 16 tables across 8 domains, all managed by Alembic version-controlled migrations:

| Domain | Tables |
|--------|--------|
| Authentication | `users`, `user_sessions` |
| Ingestion | `ingestion_runs`, `ingestion_alerts` |
| Billing | `billing_records` |
| Anomaly Detection | `anomalies` |
| AI Recommendations | `recommendations` |
| Tenant Attribution | `tenant_profiles`, `allocation_rules`, `tenant_attributions` |
| Budgets & Alerts | `budgets`, `budget_thresholds`, `alert_events` |
| Notifications | `notification_channels`, `notification_deliveries` |
| System | `alembic_version` |

Every table uses a UUID primary key. The full schema is documented in `docs/DB_SCHEMA.sql`.

### 1.6 Background Scheduler

APScheduler manages four background jobs registered in the FastAPI lifespan function:

| Job | Schedule | Trigger |
|-----|----------|---------|
| Billing ingestion | Every 4 hours | Scheduler or manual admin trigger |
| AI recommendations | Daily at 02:00 UTC | Scheduler or manual admin trigger |
| Budget threshold checks | Every 4 hours, 1-hour offset after ingestion | Scheduler only |
| Webhook retry | Every 15 minutes | Scheduler only |

The `coalesce=True` setting collapses missed executions — if the API was offline for 3 hours, only one ingestion fires on restart rather than three back-to-back runs.

---

## 2. E-R Diagram

### 2.1 ERD Screenshot

The entity-relationship diagram below was produced using draw.io and shows all 15 application tables, their columns, primary keys (PK), foreign keys (FK), unique constraints (UK), and relationships. Solid blue lines represent actual PostgreSQL `FOREIGN KEY` constraints. Dashed green lines represent logical/soft references enforced at the application layer rather than via database constraints.

![CloudCost Full Entity Relationship Diagram](<ERD_FULL.drawio.png>)

*(File: `docs/ERD_FULL.drawio` — open at app.diagrams.net for the fully editable version)*

### 2.2 Third Normal Form (3NF) Compliance

**1NF — First Normal Form: Satisfied**

Every column in every table holds a single atomic value. There are no repeating groups. All tables have a single-column UUID primary key. Three intentional JSON/JSONB columns are noted below under the 3NF trade-off discussion.

**2NF — Second Normal Form: Satisfied**

Because every primary key is a single-column UUID, partial dependency is structurally impossible. The natural composite uniqueness constraint on `billing_records` — `(usage_date, subscription_id, resource_group, service_name, meter_category)` — is enforced as a `UNIQUE` constraint on a surrogate UUID row, not as the PK itself.

**3NF — Third Normal Form: Satisfied, with three documented trade-offs**

No non-key column transitively depends on a non-key column through another non-key column.

**Trade-off 1: `alert_events.budget_amount` and `alert_events.threshold_percent`**

These values also exist in `budgets.amount_usd` and `budget_thresholds.threshold_percent`. They are intentionally duplicated at trigger time to create an immutable audit record. A budget's configured amount can be edited after an alert fires; the event row must preserve the exact values at the moment of triggering. This is a deliberate point-in-time snapshot pattern.

**Trade-off 2: `recommendations` resource identity columns**

The columns `resource_name`, `resource_group`, `subscription_id`, `service_name`, and `meter_category` mirror columns in `billing_records` but carry no foreign key. Recommendations are generated daily from an aggregated view and the inline identity avoids a join to a potentially large `billing_records` table on every dashboard load. Accepted because recommendation rows are fully replaced each generation cycle.

**Trade-off 3: `tenant_attributions.top_service_category`**

Derivable by querying `billing_records` grouped by tenant, year, month, and service. Stored inline for O(1) dashboard reads. Recomputed on every attribution run, so staleness is bounded to the 4-hour ingestion interval.

### 2.3 Table Summary

| Table | Rows | Key Relationships |
|-------|------|-------------------|
| `users` | User accounts, RBAC roles | Parent of `user_sessions`, `notification_channels`, `budgets` |
| `user_sessions` | Refresh token registry | FK → `users` (CASCADE DELETE) |
| `billing_records` | Azure billing fact table | Logical parent of anomalies, recommendations, attributions |
| `ingestion_runs` | Ingestion job history | Logical reference to `billing_records` by date range |
| `ingestion_alerts` | Ingestion failure alerts | Standalone; linked logically to ingestion runs |
| `anomalies` | Detected cost spikes | Logical reference to `billing_records` by (service, resource_group, date) |
| `recommendations` | LLM optimization recommendations | Logical reference to `billing_records` resource identity |
| `tenant_profiles` | Tenant registry | Logical reference to `billing_records.tag` |
| `allocation_rules` | Cost allocation configuration | Logical reference to tenants |
| `tenant_attributions` | Monthly per-tenant cost totals | Logical reference to `tenant_profiles` by (tenant_id, year, month) |
| `budgets` | Budget definitions | FK → `users` (owner); parent of `budget_thresholds`, `alert_events` |
| `budget_thresholds` | Threshold percentages per budget | FK → `budgets` and `notification_channels` |
| `alert_events` | Historical threshold breach log | FK → `budgets` and `budget_thresholds` |
| `notification_channels` | Email / webhook channel config | FK → `users` (owner); parent of `notification_deliveries` |
| `notification_deliveries` | Delivery attempt log | FK → `notification_channels`; logical reference to alert_events and anomalies |

---

## 3. Project Scoping Document

### 3.1 Project Identification

| Field | Value |
|-------|-------|
| Project Title | Cloud Infrastructure Cost Optimization Platform (CloudCost) |
| Sponsor | Fileread — seed-stage legal tech startup (~$2.5M ARR, ~30 Azure tenants) |
| Student | Tsun Shan Ho |
| Advisor | Dr. Samson Ogola |
| Implementation Phase | January 2026 – April 2026 (approximately 10–11 weeks) |
| Development Model | Solo developer, part-time (~10–20 hours/week) |

### 3.2 Original Scope (CS 700, Fall 2025 Design)

The original CS 700 project proposal included six core functionality modules with multi-cloud support (Azure, AWS, GCP):

1. Real-Time Cost Monitoring Dashboard
2. Predictive Resource Scaling Engine (custom ML models)
3. Multi-Tenant Cost Attribution System
4. Automated Resource Optimization Workflows
5. Compliance and Governance Module
6. Integration Hub (Terraform, Kubernetes, DataDog, GitHub Actions, Slack, PagerDuty)

### 3.3 Scope Changes and Rationale

Following a systematic value-to-effort analysis at the beginning of CS 701, the scope was strategically revised to focus on three high-impact modules with Azure-only support.

| Module | CS 700 Decision | CS 701 Decision | Rationale |
|--------|----------------|----------------|-----------|
| Cost Monitoring Dashboard | DESIGN | **BUILD** | Foundational — all other modules depend on billing data flowing in |
| Predictive Scaling Engine | DESIGN (custom ML) | **BUILD** (LLM-based pivot) | LLM approach eliminates training data requirements and MLOps infrastructure |
| Multi-Tenant Attribution | DESIGN | **BUILD** (simplified tag-based) | Fileread needs per-tenant unit economics; tag-based approach is feasible solo |
| Automated Optimization Workflows | DESIGN | **DEFER** | High risk of production outages; automation without approval workflows is dangerous |
| Compliance and Governance | DESIGN | **DEFER** | Full SOC 2/HIPAA policy engines exceed a 10-week solo timeline |
| Integration Hub | DESIGN | **DEFER** | Lowest value-to-effort ratio; each integration is its own mini-project |
| Multi-cloud (AWS, GCP) | DESIGN | **DEFER** | Triples integration work; Fileread is Azure-only |

**Key pivot:** The Predictive Scaling Engine was redesigned from a custom ML training approach to an LLM-based recommendation engine using Anthropic Claude. This reduced effort from months of training data collection and model validation to prompt engineering against an existing API. Fileread already had Azure OpenAI infrastructure, making this a practical choice.

### 3.4 Actual Implementation vs. Revised Scope

The final implementation delivered all three committed modules plus two additional subsystems that emerged during development:

| Feature | Revised Scope | Delivered |
|---------|--------------|-----------|
| Azure Cost Management API ingestion | In scope | ✓ Implemented — 4-hour schedule, 24-month backfill, idempotent upsert |
| Real-time cost monitoring dashboard | In scope | ✓ Implemented — MTD summary, daily trend, service breakdown, top resources |
| Budget configuration and alerting | In scope | ✓ Implemented — per-subscription/tenant budgets, multiple threshold percentages |
| LLM-based cost recommendations | In scope | ✓ Implemented — Claude Sonnet 4.6 with Azure OpenAI fallback |
| Anomaly detection | In scope | ✓ Implemented — 30-day rolling baseline, auto-resolve, severity classification |
| Tag-based multi-tenant attribution | In scope | ✓ Implemented — priority-ordered rules, drag-to-reorder, per-tenant reports |
| REST API with webhook/email alerts | In scope | ✓ Implemented — HMAC-signed webhooks, SMTP email, 3-attempt retry |
| Append-only audit logging | In scope (basic) | Partial — ingestion run log and notification delivery log implemented; no general audit trail |
| Automated resource optimization | Deferred | Not implemented |
| Compliance and governance module | Deferred | Not implemented |
| Integration hub | Deferred | Not implemented |
| AWS / GCP multi-cloud support | Deferred | Not implemented |

### 3.5 Final In-Scope Statement

**Implemented:**
- Azure Cost Management API integration with incremental ingestion and 24-month historical backfill
- Real-time cost monitoring dashboard (MTD summary, trend chart, service breakdown, top resources)
- Statistical anomaly detection with severity classification and email/webhook alerts
- AI-powered optimization recommendations using Anthropic Claude Sonnet 4.6 with Azure OpenAI fallback
- Tag-based multi-tenant cost attribution with priority-ordered allocation rules
- Per-tenant monthly cost reporting with top service category and month-over-month delta
- Budget management with configurable threshold percentages and notification channels
- JWT + HttpOnly refresh-token authentication with four RBAC roles (admin, devops, finance, viewer)
- Brute-force login lockout, Argon2 password hashing, HMAC-signed webhooks

**Design Documentation Only (from CS 700):**
- Automated resource optimization workflows
- Full compliance and governance module
- Integration hub (Terraform, Kubernetes, DataDog, etc.)
- Multi-cloud architecture for AWS and GCP

**Explicitly Out of Scope:**
- Direct cloud resource provisioning or automated execution of optimization actions
- Custom ML model training
- Full SOC 2, HIPAA, or GDPR compliance engines
- On-premises infrastructure support

### 3.6 Success Criteria Assessment

| Criterion | Target | Achieved |
|-----------|--------|----------|
| Functional implementation of three core modules | End-to-end demonstration | ✓ All three modules functional |
| Comprehensive test suite | Automated tests | ✓ 286 tests (170 backend + 116 frontend), 99.7% pass rate |
| Zero open bugs at submission | 0 open bugs | ✓ 9 bugs tracked and resolved |
| Production-ready security | No critical vulnerabilities | ✓ 7 security vulnerabilities identified and patched |
| Platform stable enough for production | Deployable | ✓ Docker Compose (dev) + Azure Container Apps (prod) configuration complete |

---

## 4. Data Flow Diagrams

### 4.1 Level 0 — Context Diagram

The context diagram shows the CloudCost Platform as a single process surrounded by six external entities. It establishes the system boundary: what goes in, what comes out, and who/what interacts with it.

![DFD Level 0 - Context Diagram](<DFD-Level 0 - Context.drawio.png>)

*(File: `docs/DFD.drawio`, Page 1 — open at app.diagrams.net)*

**External Entities:**

| ID | Entity | Role |
|----|--------|------|
| E1 | Azure Cost Management API | Source of raw billing data. The platform queries it on a date-range window and receives daily cost records per resource. |
| E2 | Admin / DevOps User | Operators who log in, trigger ingestion, configure budgets, and review anomaly dashboards. |
| E3 | Finance / Viewer User | Read-only stakeholders who view cost reports, tenant breakdowns, and AI recommendations. |
| E4 | Anthropic Claude / Azure OpenAI | External LLM APIs. The platform sends a 30-day cost history prompt and receives a structured optimization recommendation. Azure OpenAI acts as a fallback when Anthropic fails all retries. |
| E5 | SMTP Server | Outbound email relay for budget, anomaly, and ingestion failure alerts. |
| E6 | Webhook Endpoints | Customer-configured HTTP endpoints. The platform sends HMAC-SHA256-signed JSON payloads for the same three alert types, retrying failures every 15 minutes up to three total attempts. |

**Key Data Flows at the System Boundary:**

| Direction | Data |
|-----------|------|
| E1 → Platform | Raw billing records (daily cost per subscription, resource group, service, meter category) |
| Platform → E1 | Parameterized billing query (date range + subscription scope) |
| E2/E3 → Platform | Login credentials; admin commands; filter parameters |
| Platform → E2/E3 | JWT access token + HttpOnly refresh cookie; dashboard data; recommendations |
| Platform → E4 | Resource metadata + 30-day cost history prompt |
| E4 → Platform | Structured recommendation: `{category, explanation, estimated_monthly_savings, confidence_score}` |
| Platform → E5 | Rendered HTML email alerts |
| Platform → E6 | HMAC-signed JSON webhook payloads |

---

### 4.2 Level 1 — Expanded DFD

The Level 1 diagram decomposes the platform into eight internal processes (P1–P8) and seven data stores (D1–D7), showing every significant data flow between them.

![DFD Level 1 - Expanded Data Flow Diagram](<DFD-Level 1 - DFD.drawio (1).png>)

*(File: `docs/DFD.drawio`, Page 2 — open at app.diagrams.net)*

**Processes:**

| ID | Process | Schedule / Trigger |
|----|---------|-------------------|
| P1 | Authenticate Users | On login request from E2 or E3 |
| P2 | Ingest Billing Data | Every 4 hours; manual trigger from E2 |
| P3 | Monitor Costs | On-demand query from E2 or E3 |
| P4 | Detect Anomalies | Post-ingestion hook called by P2 |
| P5 | Generate AI Recommendations | Daily at 02:00 UTC; manual trigger from E2 |
| P6 | Attribute Tenant Costs | Post-ingestion hook called by P2 |
| P7 | Check Budget Thresholds | Every 4 hours, 1-hour offset after ingestion |
| P8 | Deliver Notifications | Called by P4, P7, and P2 on ingestion failure |

**Data Stores:**

| ID | Store | Contents |
|----|-------|----------|
| D1 | `billing_records` | Primary fact table: one row per (usage_date, subscription_id, resource_group, service_name, meter_category) |
| D2 | `users` / `user_sessions` | User accounts (Argon2-hashed passwords, roles) and refresh-token session rows |
| D3 | `anomalies` | Detected cost spikes with baseline metrics, deviation percentage, severity, and lifecycle status |
| D4 | `recommendations` + Redis cache | LLM recommendation rows keyed by resource identity and `generated_date`; Redis holds 24-hour cache entries and daily call counter |
| D5 | `tenant_profiles` / `allocation_rules` / `tenant_attributions` | Tenant registry, allocation rule configuration, and computed monthly attribution results |
| D6 | `budgets` / `budget_thresholds` / `alert_events` | Budget definitions, threshold percentages, and historical alert event log |
| D7 | `notification_channels` / `notification_deliveries` | Channel configuration and full delivery log with retry state |

**Key Flows:**

| Flow Path | Description |
|-----------|-------------|
| E2 → P1 → D2 → E2 | Login authenticated, session written, token returned |
| E1 → P2 → D1 | Billing records fetched, mapped, and upserted idempotently |
| P2 → P4 | Post-ingestion anomaly detection triggered synchronously |
| P2 → P6 | Post-ingestion tenant attribution triggered synchronously |
| D1 → P4 → D3 → P8 → D7 → E5/E6 | Anomaly detected, upserted, notification dispatched |
| D1 → P5 ↔ D4 ↔ E4 | Recommendations generated from billing data with Redis caching and LLM call |
| D1 → P6 ↔ D5 | Tagged spend partitioned by tenant, rules applied, attribution upserted |
| D6 → P7 → D6 + P8 | Active budgets read, spend compared, alert events written, notifications dispatched |
| P8 → D7 + E5/E6 | Delivery logged; webhook payloads HMAC-signed before POST |

---

## 5. Network Diagram

### 5.1 Network Diagram Screenshot

The network diagram below shows the CloudCost production architecture deployed on Microsoft Azure. Components with a solid border are currently implemented. Components with a dashed border and `[PLANNED]` label are designed and architecturally specified but not yet deployed.

![CloudCost Production Network Architecture on Azure](<NETWORK-Prod - Azure Architecture.drawio (2).png>)

*(File: `docs/NETWORK.drawio`, Page 2 — open at app.diagrams.net. Page 1 of the same file shows the local Docker Compose development topology.)*

### 5.2 Component Justification

#### Edge / Public Layer

| Component | Status | Justification |
|-----------|--------|--------------|
| **Azure Front Door** | Implemented | Global load balancer and CDN at the Azure network edge. Terminates SSL/TLS, distributes traffic to the nearest Container App region, and provides DDoS protection at the network level. Required for production availability and latency. |
| **WAF (Web Application Firewall)** | Planned | Azure Front Door integrates with Azure Web Application Firewall to filter OWASP Top 10 attack patterns (SQL injection, XSS, CSRF). Not yet enabled due to the cost of WAF rules at the current scale, but the architecture is pre-integrated. |

#### Application Layer

| Component | Status | Justification |
|-----------|--------|--------------|
| **React Frontend (Container App)** | Implemented | The React 19 SPA is served as a static build from an Azure Container App. Container Apps provides auto-scaling from zero, eliminating idle compute costs. No VM management required. |
| **FastAPI Backend (Container App)** | Implemented | The FastAPI API server runs as an Azure Container App. Supports horizontal scaling (1–3 replicas). Uses the same Docker image built for local development via Docker Compose, ensuring environment parity. |

#### Data Layer

| Component | Status | Justification |
|-----------|--------|--------------|
| **PostgreSQL Flexible Server (Primary)** | Implemented | Azure Database for PostgreSQL Flexible Server provides managed PostgreSQL 15 with automated backups, point-in-time restore, and high availability. Eliminates manual database administration. |
| **PostgreSQL Flexible Server (Read Replica)** | Planned | A read replica will offload cost reporting and dashboard queries from the primary server as query volume grows. Not yet provisioned at current scale (~30 tenants). |
| **Azure Cache for Redis** | Implemented | Managed Redis 7 instance for recommendation caching (24-hour per-resource TTL) and daily LLM call counter. The managed service handles failover and patching. |
| **Azure Container Registry** | Implemented | Private Docker registry storing built images for both the API and frontend services. Required for secure container deployment from GitHub Actions CI/CD. |

#### Management and Security Layer (All Planned)

| Component | Status | Justification |
|-----------|--------|--------------|
| **Azure VPN Gateway** | Planned | A site-to-site VPN tunnel between the production Azure virtual network and Fileread's on-premises network will allow administrative access without exposing management ports to the public internet. |
| **Azure Bastion** | Planned | Managed bastion service provides browser-based RDP/SSH access to virtual machines without a public IP. Eliminates the attack surface of exposed management ports. |
| **Azure Key Vault** | Planned | Centralized secret management for API keys (Anthropic, Azure OpenAI, SMTP, HMAC webhook secrets). Currently secrets are injected via Container App environment variables; Key Vault provides rotation and audit logging. |
| **Microsoft Sentinel (SIEM)** | Planned | Cloud-native SIEM for aggregating logs from all Azure resources, detecting suspicious patterns (e.g., repeated failed authentication, unusual API call volumes), and correlating security events. |
| **Microsoft Defender (IDS)** | Planned | Azure Defender for Containers monitors running container workloads for known attack patterns and anomalous behavior. Provides intrusion detection at the host level. |
| **Azure Monitor + Log Analytics** | Planned | Centralized logging and alerting for application metrics, container health, database performance, and custom metrics (ingestion run durations, LLM call rates). |

#### CI/CD

| Component | Status | Justification |
|-----------|--------|--------------|
| **GitHub Actions** | Implemented | CI/CD pipeline runs lint, type-check, format verification, and all 286 automated tests on every push. Builds Docker images and pushes to Azure Container Registry on merges to `main`. |
| **Docker Build** | Implemented | Multi-stage Dockerfiles for both backend and frontend minimize image size. The same images are used in CI, local Docker Compose, and production Container Apps. |

### 5.3 Development Network (Docker Compose)

For local development, all services run in a single Docker Compose network (`app_network`) on the developer's machine. This eliminates the need for Azure credentials during feature development.

| Container | Port Exposed | Role |
|-----------|-------------|------|
| `frontend` (React + Vite) | 3000 (host) | Serves the React SPA with hot-module replacement |
| `api` (FastAPI + uvicorn) | 8000 (host) | Backend API with `MOCK_AZURE=true` for synthetic billing data |
| `db` (PostgreSQL 15) | Internal only | Primary data store (accessible on host only during development) |
| `redis` (Redis 7) | Internal only | Cache and counter store |
| `migrate` (Alembic) | — | One-shot service; runs `alembic upgrade head` and exits |
| `seed` (Python script) | — | One-shot service; seeds admin account and exits |

External service calls (Azure Cost Management API, Anthropic Claude, Azure OpenAI) are mocked in development mode. The `MOCK_AZURE=true` setting causes the ingestion service to return synthetic billing records, and the LLM services use configurable API keys from `.env.local`.

---

## 6. Security Measures

### 6.1 Authentication and Session Management

**JWT Access Tokens**
- Short-lived access tokens (60 minutes) are signed with HS256 using a configurable `JWT_SECRET_KEY`.
- Access tokens are returned in the JSON response body and stored only in JavaScript memory — never in `localStorage` or `sessionStorage`. This prevents XSS-based token theft via storage APIs.
- The startup configuration rejects the default development `JWT_SECRET_KEY` if `APP_ENV=production`, preventing accidental deployment with a weak secret.

**HttpOnly Refresh Tokens**
- Long-lived refresh tokens (7 days) are set as `HttpOnly`, `SameSite=Lax` cookies, making them inaccessible to JavaScript and resistant to XSS attacks.
- The raw refresh token is never stored in the database. Instead, a SHA-256 hash of the token is stored in `user_sessions`. The original token is stored only in the cookie on the client.
- Refresh tokens are invalidated server-side by setting `revoked=True` on the session row. The `/auth/refresh` endpoint checks both token expiry and revocation status before issuing a new access token.

**Token Type Enforcement**
- Every JWT carries a `type` claim (`"access"` or `"refresh"`). The `get_current_user` dependency rejects any token where `type != "access"`, preventing a refresh token from being used to authenticate API requests.

### 6.2 Brute-Force Protection

The login endpoint tracks failed attempts per user account:

- After 5 consecutive failed login attempts, the account is locked for 15 minutes (`locked_until = now + 15 minutes`).
- During a lockout, the endpoint returns HTTP 429 ("Account temporarily locked") before attempting password verification, avoiding unnecessary Argon2 computation.
- On a successful login, both the failed attempt counter and the lockout timestamp are reset.
- The lockout is per-account (not per-IP) to prevent distributed brute-force attacks from bypassing an IP-based block.

### 6.3 Password Security

- All passwords are hashed using **Argon2id** via the `passlib` library. Argon2id is the winner of the Password Hashing Competition and is resistant to GPU-based attacks due to its configurable memory hardness.
- Password hashes are never returned in any API response.

### 6.4 Role-Based Access Control (RBAC)

Four roles control access to all API endpoints:

| Role | Access Level |
|------|-------------|
| `admin` | Full access to all features including user management and system configuration |
| `devops` | Full access to ingestion, recommendations, anomalies; cannot manage users |
| `finance` | Read-only access to cost data, attributions, and recommendations |
| `viewer` | Read-only access to cost dashboards only |

RBAC is enforced via FastAPI dependency injection (`require_admin`, `get_current_user`) at the route level, not via middleware. This provides fine-grained per-endpoint control.

An **IDOR (Insecure Direct Object Reference)** fix was applied to the budget threshold deletion endpoint: the endpoint verifies that the threshold being deleted belongs to a budget owned by the requesting user before allowing the deletion.

### 6.5 Webhook Security

- All outbound webhook payloads are signed with **HMAC-SHA256** using a per-channel secret. The signature is sent in the `X-CloudCost-Signature` HTTP header.
- Webhook secrets are stored in the database and **redacted from all API responses** — the `config_json` field is masked before serialization so that an authenticated user who can read channel configuration cannot retrieve the raw secret.
- Failed webhook deliveries store the original signed payload in `notification_deliveries.payload_json` for retry. Retries re-sign with a fresh HMAC computation using the stored secret.

### 6.6 Input Validation

- All request bodies pass through **Pydantic** schemas before reaching route handlers. FastAPI returns HTTP 422 with a structured error detail array for any validation failure.
- Pydantic validates data types, required fields, string lengths, and enumerated values. No manual input validation is needed in route handlers.

### 6.7 HTTPS and Transport Security

- All production traffic terminates at Azure Front Door, which enforces TLS 1.2+ and provides free managed certificates.
- Internal communication between Container Apps is routed through Azure's internal network and does not traverse the public internet.
- The development environment uses HTTP (no TLS) — this is acceptable for `localhost` traffic only and is enforced by the `APP_ENV` check.

### 6.8 Secret Management

- All secrets (JWT key, database credentials, API keys, SMTP passwords, webhook secrets) are injected via environment variables and documented in `.env.example` with safe placeholder values.
- The `.gitignore` covers all `.env` file variants, `.env.local`, and `.env.*` patterns to prevent accidental credential commits.
- A security audit conducted on 2026-03-14 verified that no real credentials exist in any tracked source file (see `docs/SECURITY_AUDIT.md`).
- **Recommended production upgrade:** Migrate all secrets to **Azure Key Vault** with Container App secret injection via managed identity. This is architecturally specified (shown in the network diagram) and planned for a future sprint.

### 6.9 Security Vulnerabilities Identified and Resolved

A dedicated architecture security review on 2026-03-14 identified and patched seven vulnerabilities:

| ID | Vulnerability | Resolution |
|----|--------------|------------|
| CRIT-05 | Webhook HMAC secret exposed in API responses | Redacted secret fields from all API response schemas |
| CRIT-06 | Brute-force lockout logic was dead code (never enforced) | Wired lockout check into login endpoint |
| CRIT-02 | Shared SQLAlchemy session in budget check loop — `session.rollback()` corrupted subsequent iterations | Switched to per-budget isolated database sessions |
| CRIT-01 | Anthropic client instantiated before API key validation — would crash on startup if key missing | Moved client construction to after the API key guard |
| SEC-02 | Refresh tokens never expired server-side — revocation was incomplete | Added `expires_at` check on refresh token validation |
| SEC-03 | Default JWT secret accepted in production mode | Added startup validator rejecting default secrets when `APP_ENV=production` |
| API-04 | IDOR on budget threshold deletion endpoint | Added ownership verification before allowing deletion |

### 6.10 Additional Security Measures (Planned — Not Yet in Network Diagram)

| Measure | Description |
|---------|-------------|
| Append-only audit log | A dedicated audit log table recording all write operations (budget changes, user management, manual triggers) with actor, timestamp, and before/after values. Currently partial (ingestion runs and notification deliveries are logged; general mutations are not). |
| Rate limiting | API-level rate limiting on authentication endpoints and manual trigger endpoints to prevent abuse. Currently handled only at the brute-force lockout level. Planned via Azure Front Door rate-limiting rules. |
| Structured logging | JSON-formatted log output with request IDs for correlation across services. Currently uses Python's standard `logging` module with unstructured formatting. |
| Dependency scanning | Automated `pip-audit` and `npm audit` scans in CI to catch known vulnerabilities in third-party packages. Planned for a future CI step. |

---

## Appendix A: Testing Summary

| Metric | Backend | Frontend | Total |
|--------|---------|----------|-------|
| Test files | 10 | 13 | 23 |
| Test cases | 170 | 116 | 286 |
| Passed | 170 | 116 | 286 |
| Failed | 0 | 0 | 0 |
| Pass rate | 100% | 99.1% | 99.7% |

Full testing results are documented in `docs/TESTING_RESULTS.md`.

---

## Appendix B: Bug Resolution Summary

| ID | Description | Category | Status |
|----|-------------|----------|--------|
| BUG-001 | CI test failures (jsdom missing APIs) | Testing/CI | Resolved |
| BUG-002 | GitGuardian JWT placeholder flag | Security/CI | Resolved |
| BUG-003 | Manual seed required after compose up | Developer Experience | Resolved |
| BUG-004 | Date timezone off-by-one for UTC-negative users | Frontend | Resolved |
| BUG-005 | Array index used as React key | Frontend | Resolved |
| BUG-006 | 7 security vulnerabilities (see Section 6.9) | Security | Resolved |
| BUG-007 | HTML5 drag events unreliable cross-browser | Frontend | Resolved |
| BUG-008 | Missing Alert UI component (import error) | Frontend | Resolved |
| BUG-009 | Stale `summaryParts` variable reference | Frontend | Resolved |

Full root cause analysis for each bug is documented in `docs/BUG_LIST.md`.

---

## Appendix C: Referenced Source Files

| Purpose | File |
|---------|------|
| Full database schema (SQL) | `docs/DB_SCHEMA.sql` |
| ERD (draw.io, editable) | `docs/ERD_FULL.drawio` |
| DFD (draw.io, editable) | `docs/DFD.drawio` |
| Network Diagram (draw.io, editable) | `docs/NETWORK.drawio` |
| 3NF analysis + Mermaid ERD | `docs/ERD.md` |
| DFD narrative | `docs/DFD.md` |
| Network diagram narrative | `docs/NETWORK.md` |
| Security audit | `docs/SECURITY_AUDIT.md` |
| Bug list | `docs/BUG_LIST.md` |
| Testing results | `docs/TESTING_RESULTS.md` |
| Error handling documentation | `docs/ERROR_HANDLING.md` |
| Database backup and recovery plan | `docs/BACKUP_RECOVERY.md` |
| Presentation outline | `docs/PRESENTATION_OUTLINE.md` |
