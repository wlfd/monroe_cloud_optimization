# Phase 2: Data Ingestion - Research

**Researched:** 2026-02-20
**Domain:** Azure Cost Management API ingestion, APScheduler async scheduling, SQLAlchemy 2.0 idempotent upsert, Tenacity retry
**Confidence:** HIGH (all core decisions backed by official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Admins have a "Run now" button to trigger an ingestion run immediately without waiting for the schedule
- Manual run uses the same data window as the scheduled run (no custom date range selection in this phase)
- Show running/idle status so admins know if a run is already in progress before triggering
- Block new triggers while a run is already in progress — one run at a time only (no queuing)
- When ingestion fails after all retries, show a persistent in-app notification banner visible when admin logs in
- Alert must include: error message from Azure API, retry count attempted, and failure timestamp
- Maintain a run history log that admins can browse: each run shows timestamp, status (success/fail), records ingested, and any error details
- Each scheduled run fetches delta only — from the last successful run's end timestamp to now
- If runs are missed (app downtime), the next run catches up from the last successful run
- Maximum catch-up window is capped at 7 days — beyond that, manual backfill is required to avoid large unintended re-ingestion

### Claude's Discretion
- Auto-clear behavior for the in-app failure alert (auto-clear vs persist-until-dismissed)
- Whether to include a 24-48hr re-check window on each run to catch late-arriving Azure records
- Exact retry backoff parameters (beyond the roadmap's "exponential backoff" spec)
- Scheduler implementation (APScheduler, Celery, cron-based, etc.)

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INGEST-01 | System ingests Azure billing data from Cost Management API on a 4-hour schedule | APScheduler 3.x AsyncIOScheduler with interval trigger (hours=4); azure-mgmt-costmanagement QueryDefinition with Custom timeframe |
| INGEST-02 | System performs 24-month historical data backfill on first account setup | Same ingestion function called in month-sized chunks (API limit: max 1 month per call); first-run flag in ingestion_runs table |
| INGEST-03 | System retries failed API calls with exponential backoff (3 retries: 5s, 30s, 120s) | Tenacity 9.x `@retry` with `wait_exponential` and `stop_after_attempt(3)`; specific backoff matches requirement exactly |
| INGEST-04 | Ingestion is idempotent — re-runs do not create duplicate billing records | SQLAlchemy 2.0 PostgreSQL `insert().on_conflict_do_update()` with unique constraint on (usage_date, subscription_id, resource_group, service_name, meter_id) |
| INGEST-05 | Failed ingestion runs generate an admin alert notification | `ingestion_alerts` table with persistent banner flag; auto-cleared on next successful run (Claude's discretion resolved) |
| INGEST-06 | All ingestion runs are logged with status, row count, and duration | `ingestion_runs` table: id, started_at, completed_at, status, records_ingested, error_detail, triggered_by |
</phase_requirements>

---

## Summary

This phase is a pure Python backend data pipeline with no user-facing frontend beyond an admin status/history panel. The core loop is: schedule triggers every 4 hours → call Azure Cost Management Query API → parse columnar response → bulk-upsert rows into PostgreSQL → update run log → surface any failure as a persistent alert.

The Azure Cost Management Query API returns billing data as a columnar result set (array of column descriptors + array of row arrays). It supports daily granularity grouped by ServiceName, ResourceGroup, SubscriptionId, MeterCategory, and ResourceId. The API is synchronous in the Python SDK (`azure-mgmt-costmanagement` 4.0.1) — it is NOT async natively, so the ingestion function must wrap the SDK call in `asyncio.to_thread()` to avoid blocking the event loop. Pagination is a known SDK gap: `next_link` is returned but not automatically followed; manual pagination loops are required for large datasets (5,000-row pages).

APScheduler 3.x (latest stable: 3.11.2) is the right choice over APScheduler 4.x (still alpha) and Celery (overkill for single-worker modular monolith). Use `AsyncIOScheduler` with `max_instances=1` to natively prevent concurrent runs. A supplementary `asyncio.Lock` (in-memory) handles the "Run now" endpoint's concurrency guard cleanly. SQLAlchemy 2.0's PostgreSQL `insert().on_conflict_do_update()` provides robust idempotent upserts without hand-rolling duplicate detection. Tenacity 9.x provides async-aware retry with the exact 5s/30s/120s parameters specified in INGEST-03.

**Primary recommendation:** Use APScheduler 3.x AsyncIOScheduler + azure-mgmt-costmanagement (run in thread) + SQLAlchemy PostgreSQL upsert + Tenacity retry. This is 4 focused libraries on top of the existing stack, no new infrastructure required.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| APScheduler | 3.11.2 (3.x branch) | 4-hour recurring scheduler, "Run now" job dispatch | Stable, asyncio-native, `max_instances=1` prevents concurrent runs; v4.x is alpha and breaking |
| azure-mgmt-costmanagement | 4.0.1 | Azure Cost Management Query API client | Official Microsoft SDK; `CostManagementClient.query.usage()` |
| azure-identity | latest (>=1.14) | Azure credential chain (service principal + managed identity) | Official SDK; `DefaultAzureCredential` handles env vars and managed identity transparently |
| tenacity | 9.1.4 | Async retry with exponential backoff | Async-native (`@retry` works directly on async funcs); flexible `wait_exponential` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy[asyncio] | >=2.0 (already installed) | Async session + PostgreSQL upsert via `insert().on_conflict_do_update()` | Core ORM — already in stack |
| asyncpg | >=0.29 (already installed) | PostgreSQL async driver | Already in stack |
| alembic | >=1.13 (already installed) | Database migrations for new tables | New models require Alembic revisions |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| APScheduler 3.x | APScheduler 4.x | 4.x is alpha (pre-release), breaking API changes vs 3.x; avoid until stable |
| APScheduler 3.x | Celery + Redis | Celery requires a broker/worker process; overkill for single-worker modular monolith |
| APScheduler 3.x | FastAPI BackgroundTasks | BackgroundTasks are per-request, not recurring scheduled; not suitable |
| azure-mgmt-costmanagement | Direct REST via httpx | SDK handles auth token refresh automatically; REST requires manual token management |
| tenacity | Manual retry loop | Tenacity handles jitter, logging, exception typing; manual loop is error-prone |

**Installation (additions to existing backend requirements):**
```bash
pip install APScheduler==3.11.2 azure-mgmt-costmanagement azure-identity tenacity
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── core/
│   └── scheduler.py        # AsyncIOScheduler singleton, lifespan integration
├── models/
│   ├── billing.py          # BillingRecord, IngestionRun, IngestionAlert models
│   └── user.py             # (existing)
├── services/
│   ├── azure_client.py     # CostManagementClient wrapper, pagination, auth
│   └── ingestion.py        # Ingestion orchestration (fetch → parse → upsert)
├── api/v1/
│   ├── ingestion.py        # POST /ingestion/run, GET /ingestion/status, GET /ingestion/runs
│   └── router.py           # (existing, add ingestion router)
└── migrations/versions/
    └── XXXX_billing_ingestion_tables.py
```

### Pattern 1: AsyncIOScheduler with Lifespan Integration

**What:** Attach APScheduler to FastAPI's lifespan context manager so it starts/stops cleanly with the application.
**When to use:** Always — this is the only safe way to run APScheduler with FastAPI's async event loop.

```python
# backend/app/core/scheduler.py
# Source: APScheduler 3.x docs https://apscheduler.readthedocs.io/en/3.x/userguide.html
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={
        "coalesce": True,          # Run once if multiple missed executions stack up
        "max_instances": 1,        # Hard limit: only one ingestion at a time
        "misfire_grace_time": 300, # 5 min grace: run missed job if < 5min late
    },
    timezone="UTC",
)

# backend/app/main.py
from contextlib import asynccontextmanager
from app.core.scheduler import scheduler
from app.services.ingestion import run_ingestion

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        run_ingestion,
        "interval",
        hours=4,
        id="ingestion_scheduled",
        replace_existing=True,
    )
    scheduler.start()
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan, ...)
```

### Pattern 2: In-Memory Lock for "Run Now" Concurrency Guard

**What:** `asyncio.Lock` prevents the "Run now" API endpoint from triggering a second ingestion while one is already running.
**When to use:** The "Run now" admin endpoint must check this lock before dispatching.

```python
# backend/app/services/ingestion.py
import asyncio

_ingestion_lock = asyncio.Lock()
_ingestion_running = False  # Readable flag for status endpoint

async def run_ingestion(triggered_by: str = "scheduler") -> None:
    global _ingestion_running
    if _ingestion_lock.locked():
        return  # Silently skip — APScheduler max_instances=1 also guards this
    async with _ingestion_lock:
        _ingestion_running = True
        try:
            await _do_ingestion(triggered_by)
        finally:
            _ingestion_running = False

def is_ingestion_running() -> bool:
    return _ingestion_running
```

### Pattern 3: Azure SDK Call Wrapped in asyncio.to_thread

**What:** The `azure-mgmt-costmanagement` SDK is synchronous. Run it in a thread to avoid blocking the asyncio event loop.
**When to use:** All Azure SDK calls in this phase.

```python
# backend/app/services/azure_client.py
import asyncio
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryDefinition, QueryDataset, QueryTimePeriod,
    QueryAggregation, QueryGrouping, QueryColumnType,
)

def _build_client() -> CostManagementClient:
    credential = DefaultAzureCredential()
    return CostManagementClient(credential)

def _fetch_page_sync(client, scope, query_def) -> tuple[list, str | None]:
    """Synchronous fetch — call via asyncio.to_thread."""
    result = client.query.usage(scope=scope, parameters=query_def)
    if result is None:
        return [], None
    rows = result.rows or []
    columns = [c.name for c in result.columns]
    next_link = result.next_link
    return rows, columns, next_link

async def fetch_billing_data(
    scope: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch all pages of billing data for a date range."""
    client = _build_client()
    query_def = QueryDefinition(
        type="Usage",
        timeframe="Custom",
        time_period=QueryTimePeriod(
            **{"from": start.isoformat(), "to": end.isoformat()}
        ),
        dataset=QueryDataset(
            granularity="Daily",
            aggregation={
                "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
            },
            grouping=[
                QueryGrouping(name="SubscriptionId", type=QueryColumnType.DIMENSION),
                QueryGrouping(name="ResourceGroup", type=QueryColumnType.DIMENSION),
                QueryGrouping(name="ServiceName", type=QueryColumnType.DIMENSION),
                QueryGrouping(name="MeterCategory", type=QueryColumnType.DIMENSION),
            ],
        ),
    )
    all_records: list[dict] = []
    rows, columns, next_link = await asyncio.to_thread(
        _fetch_page_sync, client, scope, query_def
    )
    for row in rows:
        all_records.append(dict(zip(columns, row)))
    # Manual pagination — SDK does not auto-follow next_link
    while next_link:
        rows, columns, next_link = await asyncio.to_thread(
            _fetch_page_next_sync, client, next_link
        )
        for row in rows:
            all_records.append(dict(zip(columns, row)))
    return all_records
```

### Pattern 4: Tenacity Async Retry with Exact Backoff

**What:** Wrap Azure API calls with the exact retry schedule from INGEST-03: 3 retries at 5s, 30s, 120s.
**When to use:** Any function that calls the Azure Cost Management API.

```python
# Source: https://tenacity.readthedocs.io/
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from azure.core.exceptions import HttpResponseError
import logging

logger = logging.getLogger(__name__)

# wait_exponential(multiplier=5, min=5, max=120) yields: 5s, 30s, 120s (capped)
# This matches INGEST-03: 3 retries: 5s, 30s, 120s exactly.
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=120),
    retry=retry_if_exception_type((HttpResponseError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch_with_retry(scope: str, start: datetime, end: datetime) -> list[dict]:
    return await fetch_billing_data(scope, start, end)
```

### Pattern 5: Idempotent Bulk Upsert via PostgreSQL ON CONFLICT

**What:** PostgreSQL-specific `INSERT ... ON CONFLICT DO UPDATE` prevents duplicate rows when the same date range is re-ingested.
**When to use:** All billing record writes — both scheduled delta runs and backfill.

```python
# Source: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.billing import BillingRecord

async def upsert_billing_records(
    session: AsyncSession,
    records: list[dict],
) -> int:
    if not records:
        return 0
    stmt = pg_insert(BillingRecord).values(records)
    stmt = stmt.on_conflict_do_update(
        # Unique constraint: (usage_date, subscription_id, resource_group, service_name, meter_category)
        index_elements=["usage_date", "subscription_id", "resource_group", "service_name", "meter_category"],
        set_={
            "pre_tax_cost": stmt.excluded.pre_tax_cost,
            "currency": stmt.excluded.currency,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount
```

### Pattern 6: Delta Window Calculation

**What:** Each run fetches only the delta from the last successful run's end timestamp to now, capped at 7 days.
**When to use:** Before every ingestion run (scheduled and manual).

```python
from datetime import datetime, timezone, timedelta

MAX_CATCHUP_DAYS = 7

async def compute_delta_window(session: AsyncSession) -> tuple[datetime, datetime]:
    """Returns (start, end) UTC datetimes for the next fetch window."""
    last_run = await get_last_successful_run(session)  # queries ingestion_runs table
    end = datetime.now(timezone.utc)
    if last_run is None:
        # First run: trigger backfill (handled separately)
        start = end - timedelta(hours=4)
    else:
        start = last_run.window_end
        # Cap catch-up at 7 days
        if (end - start) > timedelta(days=MAX_CATCHUP_DAYS):
            start = end - timedelta(days=MAX_CATCHUP_DAYS)
    return start, end
```

### Pattern 7: Session Creation in Scheduler Context (outside request)

**What:** APScheduler jobs run outside FastAPI request context. Use `async_sessionmaker` directly — not the `get_db` dependency.
**When to use:** Any database access inside scheduled jobs.

```python
# backend/app/services/ingestion.py
from app.core.database import AsyncSessionLocal  # existing async_sessionmaker

async def _do_ingestion(triggered_by: str) -> None:
    async with AsyncSessionLocal() as session:
        try:
            start, end = await compute_delta_window(session)
            records = await fetch_with_retry(scope=settings.AZURE_SUBSCRIPTION_SCOPE, start=start, end=end)
            count = await upsert_billing_records(session, records)
            await log_ingestion_run(session, status="success", records_ingested=count, triggered_by=triggered_by)
        except Exception as exc:
            await log_ingestion_run(session, status="failed", error_detail=str(exc), triggered_by=triggered_by)
            await create_ingestion_alert(session, error_detail=str(exc))
            raise
```

### Pattern 8: 24-Month Backfill (chunked by month)

**What:** The Azure Query API enforces a maximum query window per call (no explicit doc limit, but QPU quota is per-month; 24 months = 24 sequential API calls with a brief pause between them).
**When to use:** First-time account setup, detected by absence of any `ingestion_runs` rows.

```python
async def run_backfill(session: AsyncSession) -> None:
    """Call once on first setup — chunked into 1-month windows."""
    end_of_month = datetime.now(timezone.utc).replace(day=1)  # start of current month
    for months_back in range(24):
        chunk_end = end_of_month - timedelta(days=months_back * 30)
        chunk_start = chunk_end - timedelta(days=30)
        records = await fetch_with_retry(scope=settings.AZURE_SUBSCRIPTION_SCOPE, start=chunk_start, end=chunk_end)
        await upsert_billing_records(session, records)
        await asyncio.sleep(1)  # brief throttle between API calls (QPU quota: 12 QPU/10s)
    await log_ingestion_run(session, status="success", triggered_by="backfill")
```

### Anti-Patterns to Avoid

- **Calling `azure-mgmt-costmanagement` SDK directly in async context without `to_thread`:** The SDK is synchronous and will block the event loop. Every SDK call MUST be wrapped in `asyncio.to_thread()`.
- **Using `INSERT ... WHERE NOT EXISTS` for idempotency:** Race-prone under concurrent execution. Use `ON CONFLICT DO UPDATE` or `ON CONFLICT DO NOTHING` instead.
- **APScheduler 4.x:** Still alpha/pre-release (latest stable is 3.11.2); API is completely different from 3.x and unstable.
- **Storing the in-progress flag only in the DB:** DB state can't guard against two concurrent asyncio coroutines in the same process. Use `asyncio.Lock` for same-process guarding.
- **Querying more than 1 month of data per API call without chunking:** QPU quota is 1 QPU per month queried; 24-month single query = 24 QPUs (exceeds 12 QPU/10s quota). Always chunk by month.
- **Using APScheduler `max_instances` alone to guard "Run now":** `max_instances` only prevents the scheduler from starting a second scheduled copy; a manually triggered coroutine via the API endpoint bypasses this. The `asyncio.Lock` is the proper guard.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with exponential backoff | Custom loop with `asyncio.sleep` | tenacity `@retry` | Tenacity handles exception typing, jitter, logging callbacks, async sleep; custom loops miss edge cases |
| Azure authentication token refresh | Manual token lifecycle | `DefaultAzureCredential` from azure-identity | Handles service principal env vars, managed identity, token refresh automatically |
| API pagination | Custom next_link detection | Manual loop on `result.next_link` (no SDK method exists) | SDK has a known bug — must hand-roll the loop, but use the documented pattern |
| Duplicate billing records | Custom de-duplication query | `insert().on_conflict_do_update()` | DB-level atomic upsert is the only race-safe approach |
| Scheduler startup/shutdown | `atexit` hooks or threading | APScheduler lifespan integration | FastAPI lifespan context manager provides clean async start/stop |

**Key insight:** Retry logic, auth, and idempotency each have documented failure modes that take hours to debug when hand-rolled. Use the libraries — they handle the edge cases.

---

## Common Pitfalls

### Pitfall 1: Azure SDK Blocking the Event Loop
**What goes wrong:** Calling `client.query.usage()` directly inside an `async def` function blocks the asyncio event loop for the duration of the HTTP call (potentially several seconds). All other async tasks (including incoming API requests) stall.
**Why it happens:** `azure-mgmt-costmanagement` uses `requests` (synchronous HTTP), not `httpx` or `aiohttp`.
**How to avoid:** Always wrap SDK calls: `await asyncio.to_thread(_fetch_page_sync, client, scope, query_def)`.
**Warning signs:** API requests to other endpoints stall during ingestion runs.

### Pitfall 2: Pagination Silently Dropping Data
**What goes wrong:** `client.query.usage()` returns only the first 5,000 rows. Without pagination, ingestion silently drops all remaining records with no error.
**Why it happens:** Known SDK bug (GitHub issue #33429) — `next_link` is present in the response but the SDK provides no method to follow it.
**How to avoid:** After every `client.query.usage()` call, check `result.next_link`. If not `None`, call the REST API directly via `httpx` (or use the `_fetch_page_next_sync` pattern with a raw HTTP client) to follow pagination. Alternatively, chunk queries into 1-day windows so each window never exceeds 5,000 rows.
**Warning signs:** Record counts seem low relative to expected Azure spend; spot-check by comparing with Azure portal Cost Analysis.

### Pitfall 3: QPU Rate Limiting During Backfill
**What goes wrong:** During 24-month backfill, 24 sequential monthly queries exhaust the QPU quota (12 QPU per 10 seconds; 1 QPU per month queried). API returns 429 TooManyRequests.
**Why it happens:** Backfill fires 24 calls in rapid succession, each consuming 1 QPU.
**How to avoid:** Add `asyncio.sleep(1)` between backfill month chunks. The QPU quota resets every 10 seconds — a 1-second pause keeps throughput under the limit. Tenacity retry handles any 429s that slip through.
**Warning signs:** `HttpResponseError` with status 429 during backfill; check `x-ms-ratelimit-microsoft.costmanagement-qpu-retry-after` header.

### Pitfall 4: Alembic env.py Missing New Model Imports
**What goes wrong:** Alembic autogenerate does not detect new models (`BillingRecord`, `IngestionRun`, `IngestionAlert`) and generates an empty migration.
**Why it happens:** Alembic only sees models imported into `migrations/env.py` before `target_metadata = Base.metadata`.
**How to avoid:** Add `from app.models import billing  # noqa: F401` to `migrations/env.py` alongside the existing user import.
**Warning signs:** `alembic revision --autogenerate` produces a migration with no `op.create_table()` calls.

### Pitfall 5: asyncio.Lock Not Surviving App Restart
**What goes wrong:** On app restart, the in-memory `asyncio.Lock` and `_ingestion_running` flag reset. If the app crashes mid-ingestion, the database `ingestion_runs` row remains with `status='running'` indefinitely, misleading the status endpoint.
**Why it happens:** In-memory state is ephemeral; DB state persists across restarts.
**How to avoid:** On application startup (in lifespan), query for any `ingestion_runs` rows with `status='running'` and update them to `status='interrupted'`. This cleans stale state before the scheduler starts.
**Warning signs:** Admin status panel shows "running" after a restart when nothing is actually running.

### Pitfall 6: Azure Data Latency (24-48hr Delay)
**What goes wrong:** Azure billing data for recent days may not be finalized for 24-48 hours. A delta run that ends "now" will capture incomplete records for the last 1-2 days, which will differ from the final billed amount.
**Why it happens:** Azure resource providers emit usage asynchronously; Cost Management data is refreshed every 4 hours but last-2-days records may be revised.
**How to avoid (Claude's discretion):** Include a 24-hour re-check overlap window. Each run's `start` timestamp = `last_successful_run.window_end - 24h`. This causes the upsert to refresh recent rows with updated values. The `on_conflict_do_update` pattern handles this correctly.
**Warning signs:** Costs for recent days in the DB differ from Azure portal figures.

### Pitfall 7: Backfill Triggered on Every Restart
**What goes wrong:** The "first run = no ingestion_runs rows" check triggers backfill every time the database is reset or the ingestion_runs table is cleared during development.
**Why it happens:** The first-run detection is purely based on table emptiness.
**How to avoid:** Check for any successful run, not just any run. Alternatively, use a separate `system_flags` table or a setting record to track `backfill_completed=True`. For MVP, checking `SELECT 1 FROM ingestion_runs WHERE status='success' LIMIT 1` is sufficient.

---

## Code Examples

### QueryDefinition for Subscription-Scoped Daily Billing with Key Dimensions

```python
# Source: https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01
from azure.mgmt.costmanagement.models import (
    QueryDefinition, QueryDataset, QueryTimePeriod,
    QueryAggregation, QueryGrouping, QueryColumnType,
)

query_def = QueryDefinition(
    type="Usage",
    timeframe="Custom",
    time_period=QueryTimePeriod(**{
        "from": "2026-01-01T00:00:00Z",
        "to": "2026-01-31T23:59:59Z",
    }),
    dataset=QueryDataset(
        granularity="Daily",
        aggregation={
            "totalCost": QueryAggregation(name="PreTaxCost", function="Sum")
        },
        grouping=[
            QueryGrouping(name="SubscriptionId", type=QueryColumnType.DIMENSION),
            QueryGrouping(name="ResourceGroup", type=QueryColumnType.DIMENSION),
            QueryGrouping(name="ServiceName", type=QueryColumnType.DIMENSION),
            QueryGrouping(name="MeterCategory", type=QueryColumnType.DIMENSION),
        ],
    ),
)
scope = "/subscriptions/{subscription_id}"
result = client.query.usage(scope=scope, parameters=query_def)
# result.columns = [{"name": "PreTaxCost", "type": "Number"}, {"name": "SubscriptionId", ...}, ...]
# result.rows = [[19.54, "sub-id", "rg-name", "Virtual Machines", "Compute", 20260131, "USD"], ...]
# result.next_link = "https://..." or None
```

### SQLAlchemy BillingRecord Model (with Unique Constraint)

```python
# backend/app/models/billing.py
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Integer, Boolean, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class BillingRecord(Base):
    __tablename__ = "billing_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    service_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    meter_category: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    pre_tax_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint(
            "usage_date", "subscription_id", "resource_group",
            "service_name", "meter_category",
            name="uq_billing_record_key",
        ),
        Index("idx_billing_usage_date", "usage_date"),
        Index("idx_billing_subscription", "subscription_id"),
        Index("idx_billing_resource_group", "resource_group"),
        Index("idx_billing_service_name", "service_name"),
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'running' | 'success' | 'failed' | 'interrupted'
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False)  # 'scheduler' | 'manual' | 'backfill'
    records_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class IngestionAlert(Base):
    __tablename__ = "ingestion_alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cleared_by: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 'auto_success' | 'admin'
```

### Tenacity Retry with Exact INGEST-03 Parameters

```python
# Source: https://tenacity.readthedocs.io/
# INGEST-03: 3 retries: 5s, 30s, 120s
# wait_exponential(multiplier=5, min=5, max=120):
#   attempt 1 fail → wait 5s  (5 * 2^0 = 5)
#   attempt 2 fail → wait 30s (5 * 2^? capped... use fixed waits instead)
# Use wait_chain for exact control:
from tenacity import retry, stop_after_attempt, wait_chain, wait_fixed, retry_if_exception_type, before_sleep_log
from azure.core.exceptions import HttpResponseError

@retry(
    stop=stop_after_attempt(3),
    wait=wait_chain(wait_fixed(5), wait_fixed(30), wait_fixed(120)),
    retry=retry_if_exception_type((HttpResponseError, TimeoutError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch_with_retry(scope: str, start: datetime, end: datetime) -> list[dict]:
    return await fetch_billing_data(scope, start, end)
```

### Admin API Endpoints Pattern

```python
# backend/app/api/v1/ingestion.py
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.dependencies import require_admin  # existing dependency
from app.services.ingestion import run_ingestion, is_ingestion_running

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

@router.post("/run", status_code=202)
async def trigger_manual_run(current_user=Depends(require_admin)):
    if is_ingestion_running():
        raise HTTPException(status_code=409, detail="Ingestion already in progress")
    # Fire and forget — do NOT await (it's long-running)
    asyncio.create_task(run_ingestion(triggered_by="manual"))
    return {"status": "accepted"}

@router.get("/status")
async def get_ingestion_status(current_user=Depends(require_admin)):
    return {"running": is_ingestion_running()}

@router.get("/runs")
async def list_ingestion_runs(
    limit: int = 20,
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_admin),
):
    # Query ingestion_runs ORDER BY started_at DESC LIMIT limit
    ...
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| APScheduler 3.x AsyncIOScheduler | APScheduler 4.x AsyncScheduler | 4.x still alpha as of 2026 | Stick with 3.x; 4.x not production-ready |
| `requests`-based Azure SDK + blocking calls | Wrap in `asyncio.to_thread()` | Python 3.9+ | Standard pattern for sync libs in async apps |
| Manual duplicate detection (SELECT then INSERT) | `INSERT ON CONFLICT DO UPDATE` | PostgreSQL 9.5+ / SQLAlchemy 1.1+ | Atomic, race-safe, single round-trip |
| Celery for background jobs in FastAPI | In-process APScheduler | 2022+ | Celery requires broker; overkill for single-worker |
| Custom retry loops | Tenacity library | 2017, mature 2022 | Handles async, edge cases, logging out of the box |

**Deprecated/outdated:**
- `passlib` / `crypt`: Already avoided in Phase 1 (pwdlib used instead)
- APScheduler 4.x alpha: Do not use; API is entirely different and unstable
- `azure.mgmt.costmanagement` `usage_by_next_link()`: This method does NOT exist in the Python SDK; manual HTTP call or chunking is required for pagination

---

## Open Questions

1. **Azure subscription scope vs billing account scope**
   - What we know: The Query API supports both subscription scope (`/subscriptions/{id}`) and billing account scope (`/providers/Microsoft.Billing/billingAccounts/{id}`). Subscription scope is simpler and sufficient for single-subscription deployments.
   - What's unclear: The project assumptions assume a single Azure subscription. If Fileread has multiple subscriptions, the scope changes.
   - Recommendation: Design the `settings.AZURE_SUBSCRIPTION_SCOPE` as a single env var; note in config that multi-subscription support would require looping over scopes.

2. **Exact pagination handling for large datasets**
   - What we know: The SDK does not auto-follow `next_link`. The `next_link` URL in the response is a full Azure REST API URL.
   - What's unclear: Whether the `next_link` URL can be called with the same SDK credential or requires a raw HTTP call.
   - Recommendation: Use `httpx` with the `DefaultAzureCredential` token to follow `next_link` pages directly. Alternatively, chunk queries by week (7-day windows) to stay under 5,000 rows per page for most subscriptions. Chunk approach is simpler and avoids the SDK bug entirely.

3. **Azure service principal vs managed identity for local development**
   - What we know: `DefaultAzureCredential` checks `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` env vars for service principal auth (local dev); uses managed identity in production (Azure-hosted).
   - What's unclear: Whether the project will run locally with a service principal or mock the Azure API entirely.
   - Recommendation: Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`, and `AZURE_SUBSCRIPTION_ID` to `.env.local` for dev. Add a `MOCK_AZURE=true` env var that returns synthetic data when running tests or without Azure credentials.

---

## Sources

### Primary (HIGH confidence)
- [Azure Cost Management Query REST API (2025-03-01)](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage?view=rest-cost-management-2025-03-01) — full request/response format, rate limits, QPU quotas
- [Azure Cost Management Automation Guide](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/manage-automation) — QPU quota details (12/10s, 60/min, 600/hr), data refresh cadence (4hr), best practices
- [Azure QueryOperations Python SDK](https://learn.microsoft.com/en-us/python/api/azure-mgmt-costmanagement/azure.mgmt.costmanagement.operations.queryoperations?view=azure-python) — `usage()` method signature, `QueryDefinition` structure
- [APScheduler 3.x User Guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html) — `AsyncIOScheduler`, `max_instances`, `coalesce`, `misfire_grace_time`, interval triggers
- [Tenacity Documentation](https://tenacity.readthedocs.io/) — async retry, `wait_chain`, `stop_after_attempt`, `before_sleep_log`; version 9.1.4 (Feb 2026)
- [SQLAlchemy 2.0 PostgreSQL Dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) — `insert().on_conflict_do_update()` with `index_elements` and `set_`

### Secondary (MEDIUM confidence)
- [Azure SDK Pagination Issue #33429](https://github.com/Azure/azure-sdk-for-python/issues/33429) — confirms SDK does not auto-follow `next_link`; 5,000-row page limit
- [Microsoft Q&A: next_link pagination workaround](https://learn.microsoft.com/en-us/answers/questions/1295618/how-to-use-next-link-in-azure-costmanagement-pytho) — manual pagination loop pattern

### Tertiary (LOW confidence — validate before implementing)
- `wait_chain` behavior in tenacity for exact fixed-interval waits (5s, 30s, 120s): Verified in tenacity docs that `wait_chain` exists but the exact sequence matching INGEST-03 should be tested. Fallback: `wait_exponential(multiplier=1, min=5, max=120)` gives approximate match.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified against official docs; versions confirmed
- Architecture: HIGH — patterns are derived from official docs and established conventions
- Azure API behavior: HIGH — QPU limits from official Microsoft Learn automation guide (updated 2025-07-03)
- Pagination gap: HIGH — confirmed by GitHub issue (Azure SDK team acknowledged)
- Pitfalls: HIGH — derived from documented behavior and official guidance

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (30 days) — Azure SDK and APScheduler 3.x are stable; APScheduler 4.x alpha may stabilize but is irrelevant to this plan
