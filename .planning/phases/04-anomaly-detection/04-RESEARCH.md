# Phase 4: Anomaly Detection - Research

**Researched:** 2026-02-21
**Domain:** Statistical anomaly detection (pure SQL, no ML), FastAPI CRUD patterns, React card-list UI
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Detection algorithm**: 30-day rolling baseline per (service_name, resource_group) pair. Both % deviation (20%+ above baseline) AND dollar impact threshold are required to flag an anomaly.
- **Severity tiers by estimated monthly dollar impact**:
  - Critical: $1,000+
  - High: $500–$999
  - Medium: $100–$499
  - Below $100: ignored — not stored, not surfaced
- **Anomaly placement**: Dedicated Anomalies page as new nav item (already placeholder in sidebar). Summary card on existing Dashboard showing active anomaly count + worst severity + link to Anomalies page.
- **Full browsable history** on the Anomalies page (not just current period).
- **Status workflow**: New → Investigating → Resolved / Dismissed. Auto-resolve when condition no longer present after an ingestion run.
- **Card-style list UI** (not a table). Each anomaly is a card with colored dot, service name, severity badge, status badge, generated human-readable description, resource group, detected timestamp, estimated impact in bold red, and action buttons.
- **4 KPI summary cards** at top of Anomalies page: Active Anomalies, Potential Impact ($), Resolved This Month, Detection Accuracy.
- **Severity summary badges** in section header: "1 Critical · 1 High · 1 Medium".
- **Three dropdown filters**: Service, Resource Group, Severity (All/Critical/High/Medium).
- **Export Report button** in page header.
- **Detection Configuration panel** at page bottom (read-only display of baseline period, alert threshold, minimum impact).
- **Mark as Expected**: sets `expected` flag on record, removes from active list.
- **Dismiss**: user can dismiss any anomaly at any time.

### Claude's Discretion

- Whether the Detection Configuration panel has an editable sensitivity UI or is read-only only.
- Exact behavior of the Investigate button (status transition to "Investigating" vs navigation to related resource — whichever is more useful).
- Exact behavior of Mark as Expected beyond setting `expected` flag and removing from active list.
- Detection Accuracy KPI calculation approach.

### Deferred Ideas (OUT OF SCOPE)

- None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ANOMALY-01 | System detects spending anomalies via 30-day rolling baseline per (service, resource group) pair | SQL window function approach documented in Architecture Patterns; detection runs as a post-ingestion hook |
| ANOMALY-02 | System assigns severity (Critical/High/Medium) based on estimated monthly dollar impact | Severity tiers locked by user; Python classification logic in service layer after dollar impact computed |
| ANOMALY-03 | System calculates estimated monthly dollar impact for each detected anomaly | Dollar impact = (current_daily_avg - baseline_daily_avg) × 30; computed in SQL or Python service layer |
| ANOMALY-04 | User can view a list of anomalies with severity, affected service, and dollar impact | Dedicated AnomaliesPage with card-list layout; backend GET /anomalies endpoint with filters |
</phase_requirements>

---

## Summary

Phase 4 builds anomaly detection entirely on top of the existing `billing_records` table (Phase 2). No new data source is needed. Detection uses a pure SQL statistical approach: compute the 30-day rolling average daily cost per `(service_name, resource_group)` pair, compare the most recent day's spend, flag records where the deviation is ≥20% AND the estimated monthly dollar impact meets the minimum threshold. This is well within PostgreSQL's window function capabilities and matches the project's existing SQLAlchemy + asyncpg stack.

The feature has two main parts: (1) a **detection job** that runs after each ingestion cycle and writes results to an `anomalies` table, and (2) a **CRUD API + React UI** that exposes those results. The action endpoints (dismiss, investigate, mark as expected) are simple PATCH operations on the `anomaly_status` and `expected` columns. The frontend follows the exact same pattern as Phase 3: TanStack Query hooks in a dedicated service file, shadcn/ui Card components for the card list, and Select dropdowns for filters.

The most important planning decision is where detection runs. The cleanest approach is a **post-ingestion hook** — call `run_anomaly_detection()` from inside `_do_ingestion()` in `ingestion.py` after a successful upsert. This avoids adding a separate scheduler job, keeps detection always current after data changes, and is the simplest integration point given the existing concurrency model.

**Primary recommendation:** Implement detection as a post-ingestion hook using pure SQL window functions. Store results in an `anomalies` table with a status column. Add a FastAPI router at `/anomalies`. Build the React page as `AnomaliesPage.tsx` following the DashboardPage pattern.

---

## Standard Stack

### Core (no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy (asyncio) | ≥2.0 (already installed) | Detection query + ORM model for anomalies table | Already in stack; window functions via `func.avg()` over subqueries |
| asyncpg | ≥0.29 (already installed) | PostgreSQL driver | Already in stack |
| Alembic | ≥1.13 (already installed) | Migration for new `anomalies` table | Already in stack |
| FastAPI | ≥0.115 (already installed) | API endpoints for anomalies CRUD + action routes | Already in stack |
| Pydantic | (bundled with FastAPI) | Request/response schemas | Already in stack |
| TanStack Query | ^5.90.21 (already installed) | Data fetching hooks for Anomalies page | Already in stack |
| shadcn/ui (Card, Select, Button, Skeleton) | (already installed) | Anomaly cards, filter dropdowns, action buttons | Already in stack |
| lucide-react | ^0.575.0 (already installed) | Icons (AlertTriangle already imported in sidebar) | Already in stack |

### Supporting (new shadcn components needed)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn Badge | (add via `shadcn add badge`) | Severity badges (Critical/High/Medium), status badges (New/Investigating/Resolved/Dismissed) | Anomaly cards and section header counts |
| shadcn Dialog | (add via `shadcn add dialog`) | Optional: confirm dialog for Dismiss action | Only if dismiss needs confirmation UX |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQL window functions | Python-side rolling average (fetch all rows, compute in service) | SQL is faster and keeps computation in DB; Python approach would require fetching 30+ days of raw rows into memory for every (service, resource_group) pair |
| Post-ingestion hook | Separate APScheduler job | Separate job adds complexity; post-ingestion hook is simpler and keeps detection in sync with data automatically |
| Dedicated `anomalies` table | Re-computing from `billing_records` on every API call | Stored anomalies allow status tracking (dismiss/investigate/resolve), browsable history, and fast reads; recomputing on API calls doesn't support lifecycle management |

**Installation (new shadcn components only):**
```bash
npx shadcn add badge
# npx shadcn add dialog  (only if confirmation dialogs are needed)
```

---

## Architecture Patterns

### Recommended Project Structure (new files only)

```
backend/
├── app/
│   ├── models/
│   │   └── billing.py              # ADD: Anomaly model class here (same file, follows existing pattern)
│   ├── schemas/
│   │   └── anomaly.py              # NEW: Pydantic schemas for anomaly responses + action requests
│   ├── services/
│   │   └── anomaly.py              # NEW: Detection logic + CRUD helpers
│   └── api/v1/
│       ├── anomaly.py              # NEW: FastAPI router /anomalies
│       └── router.py               # EDIT: include anomaly router
├── migrations/versions/
│   └── XXXX_add_anomalies_table.py # NEW: Alembic migration

frontend/src/
├── pages/
│   └── AnomaliesPage.tsx           # NEW: Full anomalies page
├── services/
│   └── anomaly.ts                  # NEW: TanStack Query hooks + interfaces
└── App.tsx                          # EDIT: uncomment /anomalies route
```

### Pattern 1: Anomaly Detection Algorithm (SQL Window Functions)

**What:** Compute a 30-day rolling baseline average daily cost per (service_name, resource_group) pair. Compare the most recent day's aggregated spend against that baseline. Flag rows where deviation ≥20% AND monthly impact meets threshold.

**When to use:** Called from `_do_ingestion()` in `ingestion.py` after successful upsert.

**The SQL logic (two-step approach):**

Step 1 — Compute per-(service, resource_group) daily averages over the last 30 days:

```python
# Source: SQLAlchemy docs, func aggregates + subquery pattern
from datetime import date, timedelta
from sqlalchemy import select, func

baseline_cutoff = date.today() - timedelta(days=30)

# Subquery: sum cost per (service_name, resource_group, usage_date) — last 30 days
daily_stmt = (
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

# Aggregate: avg daily cost per (service, resource_group) = baseline
baseline_stmt = (
    select(
        daily_stmt.c.service_name,
        daily_stmt.c.resource_group,
        func.avg(daily_stmt.c.daily_cost).label("baseline_avg_daily"),
    )
    .group_by(daily_stmt.c.service_name, daily_stmt.c.resource_group)
)
baseline_rows = (await session.execute(baseline_stmt)).all()
```

Step 2 — Fetch most recent day's spend per pair, compute deviation and estimated monthly impact, write anomalies:

```python
today = date.today()
# Yesterday is the last completed billing day
check_date = today - timedelta(days=1)

current_stmt = (
    select(
        BillingRecord.service_name,
        BillingRecord.resource_group,
        func.sum(BillingRecord.pre_tax_cost).label("current_daily"),
    )
    .where(BillingRecord.usage_date == check_date)
    .group_by(BillingRecord.service_name, BillingRecord.resource_group)
)
current_rows = (await session.execute(current_stmt)).all()

# Build baseline lookup dict
baseline = {
    (r.service_name, r.resource_group): float(r.baseline_avg_daily)
    for r in baseline_rows
}

for row in current_rows:
    key = (row.service_name, row.resource_group)
    baseline_avg = baseline.get(key, 0.0)
    current = float(row.current_daily)

    if baseline_avg <= 0:
        continue  # Can't compute deviation without a baseline

    pct_deviation = (current - baseline_avg) / baseline_avg * 100
    if pct_deviation < 20.0:
        continue  # Below 20% threshold — not an anomaly

    # Estimated monthly impact = excess daily cost × 30
    monthly_impact = (current - baseline_avg) * 30

    if monthly_impact < 100:
        continue  # Below noise floor — ignore

    # Classify severity
    if monthly_impact >= 1000:
        severity = "critical"
    elif monthly_impact >= 500:
        severity = "high"
    else:
        severity = "medium"

    # Generate human-readable description
    description = (
        f"Spend increased {pct_deviation:.0f}% in {row.resource_group}"
    )

    # Upsert into anomalies table (see Pattern 2)
    await upsert_anomaly(
        session,
        service_name=row.service_name,
        resource_group=row.resource_group,
        detected_date=check_date,
        baseline_daily_avg=baseline_avg,
        current_daily_cost=current,
        pct_deviation=pct_deviation,
        estimated_monthly_impact=monthly_impact,
        severity=severity,
        description=description,
    )
```

### Pattern 2: Anomaly Model (add to billing.py)

**What:** SQLAlchemy model for storing detected anomalies. Follows exact same conventions as `BillingRecord` and `IngestionRun` in the same file.

```python
# Add to backend/app/models/billing.py — same file as BillingRecord

class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detected_date: Mapped[date] = mapped_column(Date, nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)  # "Spend increased 156% in us-east-1"
    severity: Mapped[str] = mapped_column(String(50), nullable=False)  # 'critical' | 'high' | 'medium'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="new")  # 'new' | 'investigating' | 'resolved' | 'dismissed'
    expected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    baseline_daily_avg: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    current_daily_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    pct_deviation: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    estimated_monthly_impact: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        # Natural key: one anomaly per (service, resource_group, detected_date)
        # On re-detection: update impact/severity, keep existing status
        UniqueConstraint("service_name", "resource_group", "detected_date", name="uq_anomaly_key"),
        Index("idx_anomaly_status", "status"),
        Index("idx_anomaly_severity", "severity"),
        Index("idx_anomaly_detected_date", "detected_date"),
    )
```

### Pattern 3: Anomaly Upsert (idempotent, re-detection preserves status)

**What:** INSERT ... ON CONFLICT DO UPDATE — same pattern as `upsert_billing_records`. On re-detection of same (service, resource_group, date), update impact metrics but preserve the existing `status` so user actions (dismiss, investigate) are not overwritten.

```python
# In backend/app/services/anomaly.py

from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.billing import Anomaly

async def upsert_anomaly(session: AsyncSession, **kwargs) -> None:
    stmt = pg_insert(Anomaly).values(**kwargs)
    stmt = stmt.on_conflict_do_update(
        index_elements=["service_name", "resource_group", "detected_date"],
        set_={
            # Update metrics (spike may have worsened or improved)
            "baseline_daily_avg": stmt.excluded.baseline_daily_avg,
            "current_daily_cost": stmt.excluded.current_daily_cost,
            "pct_deviation": stmt.excluded.pct_deviation,
            "estimated_monthly_impact": stmt.excluded.estimated_monthly_impact,
            "severity": stmt.excluded.severity,
            "description": stmt.excluded.description,
            "updated_at": stmt.excluded.updated_at,
            # Do NOT update: status, expected — preserve user actions
        },
    )
    await session.execute(stmt)
    # Note: caller commits (matches existing pattern in ingestion.py)
```

### Pattern 4: Auto-Resolve Logic (post-ingestion hook)

**What:** After detecting current anomalies, scan for `status='new'` or `status='investigating'` anomalies that are not in the current detected set (spike has passed). Mark them as resolved automatically.

```python
async def auto_resolve_anomalies(
    session: AsyncSession,
    still_active: set[tuple[str, str]],  # set of (service_name, resource_group)
    check_date: date,
) -> None:
    """Mark anomalies as resolved if their condition is no longer present."""
    # Load open anomalies for today's check date that were NOT re-detected
    stmt = (
        select(Anomaly)
        .where(
            Anomaly.status.in_(["new", "investigating"]),
            Anomaly.detected_date == check_date,
            Anomaly.expected == False,
        )
    )
    open_anomalies = (await session.execute(stmt)).scalars().all()
    for anomaly in open_anomalies:
        key = (anomaly.service_name, anomaly.resource_group)
        if key not in still_active:
            anomaly.status = "resolved"
            anomaly.updated_at = datetime.now(timezone.utc)
    await session.commit()
```

### Pattern 5: Post-Ingestion Hook Integration

**What:** Call anomaly detection from within `_do_ingestion()` in `ingestion.py` after a successful upsert. This is the cleanest integration point.

```python
# In backend/app/services/ingestion.py — modify _do_ingestion()

from app.services.anomaly import run_anomaly_detection  # NEW import

# Inside _do_ingestion(), after upsert_billing_records():
count = await upsert_billing_records(session, records)
await run_anomaly_detection(session)  # NEW: detect anomalies after each successful ingest
await clear_active_alerts(session)
await log_ingestion_run(...)
```

`run_anomaly_detection()` is a standalone async function that uses the same `session` (already inside the `_do_ingestion` context). It must commit its own changes or the caller can commit — follow existing pattern (each service function commits its own work).

**Important:** Detection uses `AsyncSessionLocal` passed from `_do_ingestion`. Follow the existing pattern: do NOT open a new session inside `run_anomaly_detection`; accept `session: AsyncSession` as a parameter.

### Pattern 6: FastAPI Anomaly Router

**What:** Follows exact same structure as `cost.py`. Router prefix `/anomalies`, `get_current_user` dependency on all endpoints.

```python
# backend/app/api/v1/anomaly.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.anomaly import AnomalyResponse, AnomalySummaryResponse
from app.services.anomaly import get_anomalies, get_anomaly_summary, update_anomaly_status

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

@router.get("/", response_model=list[AnomalyResponse])
async def list_anomalies(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    service_name: str | None = Query(default=None),
    resource_group: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ...

@router.get("/summary", response_model=AnomalySummaryResponse)
async def anomaly_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ...

@router.patch("/{anomaly_id}/status")
async def update_status(
    anomaly_id: uuid.UUID,
    body: AnomalyStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    ...
```

### Pattern 7: Frontend Service File (anomaly.ts)

**What:** Follows exact same structure as `cost.ts`. TypeScript interfaces + `useQuery` hooks + `useMutation` for action endpoints.

```typescript
// frontend/src/services/anomaly.ts

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';

export interface Anomaly {
  id: string;
  detected_date: string;
  service_name: string;
  resource_group: string;
  description: string;
  severity: 'critical' | 'high' | 'medium';
  status: 'new' | 'investigating' | 'resolved' | 'dismissed';
  expected: boolean;
  pct_deviation: number;
  estimated_monthly_impact: number;
}

export interface AnomalySummary {
  active_count: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  total_potential_impact: number;
  resolved_this_month: number;
  detection_accuracy: number | null;
}

export function useAnomalies(filters: { severity?: string; service_name?: string; resource_group?: string }) {
  return useQuery<Anomaly[]>({
    queryKey: ['anomalies', filters],
    queryFn: async () => {
      const { data } = await api.get<Anomaly[]>('/anomalies/', { params: filters });
      return data;
    },
    staleTime: 2 * 60 * 1000,  // 2 min — anomalies change less frequently than costs
  });
}

export function useAnomalySummary() {
  return useQuery<AnomalySummary>({
    queryKey: ['anomaly-summary'],
    queryFn: async () => {
      const { data } = await api.get<AnomalySummary>('/anomalies/summary');
      return data;
    },
    staleTime: 2 * 60 * 1000,
  });
}

export function useUpdateAnomalyStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, status }: { id: string; status: string }) => {
      await api.patch(`/anomalies/${id}/status`, { status });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomalies'] });
      queryClient.invalidateQueries({ queryKey: ['anomaly-summary'] });
    },
  });
}
```

**Key:** Use `useMutation` (not `api` singleton directly) for PATCH actions because they are server state mutations that need cache invalidation. This is different from the CSV export pattern in Phase 3 which used `api` directly because it was a one-time file download, not a state change.

### Pattern 8: Dashboard Summary Card (add to DashboardPage.tsx)

**What:** A new card in the existing KPI row linking to the Anomalies page. Uses `useAnomalySummary` hook.

```typescript
// In DashboardPage.tsx — add 4th card to KPI grid, expand to sm:grid-cols-4
import { Link } from 'react-router-dom';
import { useAnomalySummary } from '@/services/anomaly';

// In the KPI cards grid:
<Card>
  <CardHeader className="pb-2">
    <CardTitle className="text-sm font-medium text-muted-foreground">
      Active Anomalies
    </CardTitle>
  </CardHeader>
  <CardContent>
    {anomalySummary.isLoading ? (
      <div className="animate-pulse bg-muted rounded h-8 w-16" />
    ) : (
      <>
        <p className="text-2xl font-bold text-destructive">
          {anomalySummary.data?.active_count ?? 0}
        </p>
        <Link to="/anomalies" className="text-xs text-muted-foreground hover:underline">
          View anomalies →
        </Link>
      </>
    )}
  </CardContent>
</Card>
```

### Anti-Patterns to Avoid

- **Recomputing anomalies on every API read**: Detection must write to the `anomalies` table. Never recompute the baseline on each GET request — too slow with 30+ days of billing data.
- **Overwriting user actions on re-detection**: The upsert must NOT update `status` or `expected` columns on conflict. Preserve user's Dismiss/Investigate actions.
- **Opening a new session inside `run_anomaly_detection`**: Follow the established project pattern — accept `session: AsyncSession` as a parameter from the caller (`_do_ingestion`). Do NOT use `AsyncSessionLocal()` inside the detection function (it's not needed; `_do_ingestion` already has a session).
- **Separate APScheduler job for detection**: Adds a second job, potential race conditions with ingestion, and unnecessary complexity. Post-ingestion hook is the right pattern.
- **Fetching all billing rows into Python for deviation computation**: Use SQL aggregates + subqueries. Do not load raw rows into Python memory to compute averages.
- **Storing `expected` anomalies without a flag**: Mark them with `expected=True` so they can be filtered from the active list but retained in history.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Severity badge colors | Custom CSS classes | shadcn Badge with `variant` or `className` override | Consistent with design system; Badge component handles padding, font, border-radius |
| Anomaly upsert | Custom INSERT + SELECT + UPDATE | PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` via `pg_insert` | Same pattern already proven in `upsert_billing_records`; handles race conditions atomically |
| Cache invalidation after PATCH | Manual refetch calls | `queryClient.invalidateQueries` in `useMutation.onSuccess` | TanStack Query handles re-fetch coordination; manual calls cause double-fetch or missed updates |
| Rolling average | Custom Python statistics library | SQL `AVG()` aggregate over subquery | SQLAlchemy already connected; pushing computation to DB is faster and avoids N+1 row fetching |

**Key insight:** The existing codebase has already solved the hardest infrastructure problems (upsert pattern, session management, scheduler integration, TanStack Query cache management). This phase slots into all of those patterns directly.

---

## Common Pitfalls

### Pitfall 1: Detection runs before data is committed

**What goes wrong:** `run_anomaly_detection(session)` is called but the `upsert_billing_records` changes haven't been committed yet, so the detection query reads stale data.

**Why it happens:** `upsert_billing_records` calls `await session.commit()` internally (line 155 in ingestion.py). Detection must run AFTER that commit. Looking at the code: `upsert_billing_records` does commit itself, so detection called after it will see fresh data. Verify the call order.

**How to avoid:** Call `run_anomaly_detection(session)` strictly after `count = await upsert_billing_records(session, records)` returns. Upsert commits internally; detection runs on a fresh read.

**Warning signs:** Detection always finds zero anomalies even with obvious spikes in seed data.

### Pitfall 2: Unique constraint on anomalies table conflicts with history requirement

**What goes wrong:** If the unique key is `(service_name, resource_group)` only (no date), only one anomaly per pair can exist — history is destroyed on each detection run.

**Why it happens:** Over-aggressive deduplication.

**How to avoid:** The unique key MUST include `detected_date`: `(service_name, resource_group, detected_date)`. Each day's detection run creates a new row (or updates the existing one for that day). History for all past dates is preserved.

**Warning signs:** Anomaly history shows only one row per service/resource_group, never grows.

### Pitfall 3: No data in `billing_records` for the baseline window

**What goes wrong:** Detection runs but finds no anomalies because there is no 30-day historical data — for example on a fresh dev environment with only a few days of seed data.

**Why it happens:** `seed_billing.py` seeds 90 days of data (well beyond 30 days), so this is fine in development. In production, the backfill covers 24 months. But if detection runs before the backfill completes, baseline queries return NULL averages.

**How to avoid:** Guard detection with a minimum data check: if `baseline_rows` is empty (no 30-day history), skip detection silently and log a warning. Do not write anomalies.

**Warning signs:** Detection runs immediately on first ingestion but finds nothing; `baseline_rows` is empty.

### Pitfall 4: Estimated monthly impact calculation direction

**What goes wrong:** Using `current_daily_cost * 30` instead of `(current_daily_cost - baseline_daily_avg) * 30` gives gross monthly cost, not the excess/anomalous impact.

**Why it happens:** The CONTEXT.md says "estimated monthly dollar impact." This means the INCREMENTAL impact (excess over baseline), not the total projected spend.

**How to avoid:** `estimated_monthly_impact = (current_daily_cost - baseline_daily_avg) * 30`. This is the dollar figure shown in red on the card ("+ $4,520").

**Warning signs:** Estimated impact on a $20/day service with a 30% spike shows "$600" (correct: excess $6/day × 30) vs "$18,000" (wrong: full cost × 30).

### Pitfall 5: Status filter excludes resolved/dismissed anomalies from history

**What goes wrong:** The default list view filters to `status='new'` only, so dismissed and resolved anomalies are invisible — but the requirement says "full browsable history."

**Why it happens:** Defaulting to active-only filter.

**How to avoid:** Default `GET /anomalies/` returns ALL anomalies ordered by `detected_date DESC`. The frontend applies client-side or query-param filtering. Resolved anomalies show with a resolved badge. Status filter dropdown includes "All" as default option.

**Warning signs:** Dismissed anomalies disappear and cannot be recovered to view.

### Pitfall 6: Investigate button ambiguity

**What goes wrong:** Clicking "Investigate" navigates away without changing status, or changes status without giving the user context.

**How to avoid (Claude's Discretion recommendation):** "Investigate" should PATCH status to "investigating" immediately (optimistic update), keeping the user on the page. The status badge changes from "new" to "investigating" visually. This is more useful than navigation because there is no resource detail page in scope for this phase. Navigation to a related resource can be a separate "View Resources" link.

**Warning signs:** Clicking Investigate causes unexpected navigation or has no visible feedback.

### Pitfall 7: DashboardPage KPI grid layout breaks

**What goes wrong:** Adding a 4th KPI card to the existing `sm:grid-cols-3` grid causes layout issues.

**How to avoid:** Change `grid-cols-1 gap-4 sm:grid-cols-3` to `grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4` in DashboardPage.tsx when adding the anomaly summary card.

**Warning signs:** 4 cards in a 3-column grid with one orphan card spanning full width on desktop.

---

## Code Examples

Verified patterns from existing codebase:

### Alembic Migration (new table, follow existing convention)

```python
# backend/migrations/versions/XXXX_add_anomalies_table.py
# Follows pattern from 50f4678d8591_add_cost_monitoring_columns.py

def upgrade() -> None:
    op.create_table(
        "anomalies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("detected_date", sa.Date(), nullable=False),
        sa.Column("service_name", sa.String(255), nullable=False),
        sa.Column("resource_group", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="new"),
        sa.Column("expected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("baseline_daily_avg", sa.Numeric(18, 6), nullable=False),
        sa.Column("current_daily_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("pct_deviation", sa.Numeric(10, 2), nullable=False),
        sa.Column("estimated_monthly_impact", sa.Numeric(18, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("service_name", "resource_group", "detected_date", name="uq_anomaly_key"),
    )
    op.create_index("idx_anomaly_status", "anomalies", ["status"])
    op.create_index("idx_anomaly_severity", "anomalies", ["severity"])
    op.create_index("idx_anomaly_detected_date", "anomalies", ["detected_date"])
```

### Severity Badge Color Mapping (frontend)

```typescript
// In AnomaliesPage.tsx or a shared utility

const severityDotColor: Record<string, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-blue-500',
};

const severityBadgeClass: Record<string, string> = {
  critical: 'bg-red-100 text-red-800 border-red-200',
  high: 'bg-orange-100 text-orange-800 border-orange-200',
  medium: 'bg-blue-100 text-blue-800 border-blue-200',
};

const statusBadgeClass: Record<string, string> = {
  new: 'bg-slate-100 text-slate-700',
  investigating: 'bg-yellow-100 text-yellow-800',
  resolved: 'bg-green-100 text-green-800',
  dismissed: 'bg-gray-100 text-gray-500',
};
```

### Pydantic Schema Pattern (follows cost.py)

```python
# backend/app/schemas/anomaly.py

from pydantic import BaseModel
from datetime import date, datetime
from uuid import UUID
from typing import Optional

class AnomalyResponse(BaseModel):
    id: UUID
    detected_date: date
    service_name: str
    resource_group: str
    description: str
    severity: str   # 'critical' | 'high' | 'medium'
    status: str     # 'new' | 'investigating' | 'resolved' | 'dismissed'
    expected: bool
    pct_deviation: float
    estimated_monthly_impact: float
    baseline_daily_avg: float
    current_daily_cost: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class AnomalySummaryResponse(BaseModel):
    active_count: int
    critical_count: int
    high_count: int
    medium_count: int
    total_potential_impact: float
    resolved_this_month: int
    detection_accuracy: Optional[float]   # null until enough history to compute

class AnomalyStatusUpdate(BaseModel):
    status: str   # 'investigating' | 'resolved' | 'dismissed'
    # Note: expected is set via a separate endpoint or combined with status

class AnomalyMarkExpectedRequest(BaseModel):
    expected: bool = True
```

### Export Pattern (follows Phase 3 CSV export)

```typescript
// In AnomaliesPage.tsx — Export Report button

const handleExport = async () => {
  setIsExporting(true);
  try {
    const response = await api.get('/anomalies/export', {
      params: { severity: selectedSeverity, service_name: selectedService },
      responseType: 'blob',
    });
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'anomaly-report.csv');
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } finally {
    setIsExporting(false);
  }
};
```

### Detection Accuracy KPI (Claude's Discretion)

The "Detection Accuracy" KPI can be computed as:

```
accuracy = (total_detected - marked_as_expected) / total_detected * 100
```

Where `marked_as_expected` counts false positives the user explicitly flagged. This is a ratio that improves as users mark false positives. When `total_detected = 0`, return `null` (display "N/A"). This is the simplest meaningful metric that doesn't require any ML.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ML-based anomaly detection (Prophet, Isolation Forest) | Statistical baseline + threshold rules | This project's scope | ML overkill for MVP; pure SQL is faster, deterministic, and debuggable |
| Celery + Redis for background jobs | APScheduler in-process (already installed) | Phase 2 decision | APScheduler already integrated; no new infrastructure needed |
| Microservices (separate detection service) | Modular monolith (Phase 1 decision) | Phase 1 design decision | Post-ingestion hook in same process; simpler deployment |

**Deprecated/outdated:**
- ML model tuning: explicitly deferred per CONTEXT.md — do NOT add any ML libraries.
- Separate notification/alerting: deferred per CONTEXT.md — no email/webhook in this phase.

---

## Open Questions

1. **Detection accuracy denominator edge case**
   - What we know: accuracy = `(detected - expected) / detected * 100`
   - What's unclear: When `total_detected = 0` (no anomalies ever detected), we'd divide by zero
   - Recommendation: Return `null` from the API when `total_detected = 0`. Frontend shows "N/A" (same pattern as `mom_delta_pct` in cost summary).

2. **What check_date to use for detection baseline**
   - What we know: Billing data is typically 1-2 days behind in Azure. The most recent complete billing day is usually `today - 1`.
   - What's unclear: If ingestion runs at midnight and yesterday's data isn't available yet, detection on `check_date = today - 1` may find no data.
   - Recommendation: Find the MAX(usage_date) in `billing_records` and use that as the check date instead of hardcoding `today - 1`. This is robust to Azure data latency.

3. **Mark as Expected behavior (Claude's Discretion)**
   - What we know: Sets `expected=True`, removes from active list.
   - Recommendation: `PATCH /{id}/expected` sets `expected=True` AND sets `status='dismissed'`. This keeps it out of active view. The anomaly is still in history with both flags set, which is clear to the user and simple to query (`WHERE expected=False AND status NOT IN ('resolved','dismissed')` = active list).

4. **Whether to add `badge` shadcn component**
   - What we know: Badge is not currently installed (not in `frontend/src/components/ui/`).
   - What's unclear: Could use inline `<span>` with className instead.
   - Recommendation: Add Badge via `npx shadcn add badge` — it's a simple component and keeps severity/status chips visually consistent with the design system. One `shadcn add` command, low risk.

---

## Sources

### Primary (HIGH confidence)

- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/backend/app/services/ingestion.py` — established session management, upsert pattern, post-ingest hook integration point
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/backend/app/services/cost.py` — SQLAlchemy async query patterns, service layer conventions
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/backend/app/models/billing.py` — ORM model conventions (UUID PK, utcnow(), UniqueConstraint, Index)
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/frontend/src/services/cost.ts` — TanStack Query hook patterns
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/frontend/src/pages/DashboardPage.tsx` — Card layout, export pattern, KPI grid
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/backend/app/api/v1/cost.py` — FastAPI router pattern with get_current_user dependency
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/frontend/src/App.tsx` — routing pattern, placeholder `/anomalies` route already commented in
- Codebase: `/Users/wlfd/Developer/monroe_cloud_optimization/frontend/src/components/AppSidebar.tsx` — `AlertTriangle` icon already imported, `/anomalies` already in `navItems`
- Codebase: `.planning/phases/04-anomaly-detection/04-CONTEXT.md` — locked decisions, severity thresholds, UI spec
- Codebase: `.planning/STATE.md` — established architectural decisions (modular monolith, session patterns, PostgreSQL upsert)

### Secondary (MEDIUM confidence)

- SQLAlchemy documentation pattern: subquery + AVG aggregate for window-like computations in async context — consistent with how `get_spend_summary` and `get_breakdown` are structured in `cost.py`
- PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` with selective column updates — established in `upsert_billing_records`; the `set_` dict pattern for preserving certain columns is standard `pg_insert` usage

### Tertiary (LOW confidence)

- None — all findings are grounded in the project's own code or are direct extrapolations of its established patterns.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies needed; all libraries already installed and used
- Architecture: HIGH — detection algorithm, model schema, and integration point are fully derived from existing codebase patterns
- Pitfalls: HIGH — specific to this codebase's data model and established conventions; verified against actual code
- Frontend patterns: HIGH — TanStack Query + shadcn Card pattern is exactly what Phase 3 used

**Research date:** 2026-02-21
**Valid until:** 2026-03-21 (30 days — stable stack, no fast-moving external dependencies)
