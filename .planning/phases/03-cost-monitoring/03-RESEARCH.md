# Phase 3: Cost Monitoring - Research

**Researched:** 2026-02-20
**Domain:** Cost analytics dashboard — FastAPI aggregate queries, recharts/shadcn charts, CSV export
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COST-01 | User can view total month-to-date Azure spend with projected month-end figure | Backend: SUM(pre_tax_cost) WHERE usage_date in current month + linear projection formula; Frontend: KPI cards in DashboardPage |
| COST-02 | User can compare current period spend to previous period (MoM) | Backend: Two-period query (current vs. prior month) returning totals and delta; Frontend: MoM delta badge on KPI card |
| COST-03 | User can view daily spend trend chart with selectable 30/60/90-day views | Backend: GROUP BY usage_date SUM endpoint with `days` query param; Frontend: shadcn chart (AreaChart via recharts) + 3-button toggle |
| COST-04 | User can break down costs by service, resource group, region, and tag | **SCHEMA GAP:** `region` and `tag` columns do not exist in BillingRecord. Requires Alembic migration + Azure client update + new breakdown endpoint grouping by dimension |
| COST-05 | User can view top 10 most expensive resources for any selected period | **SCHEMA GAP:** `resource_id` and `resource_name` columns do not exist. Requires Alembic migration + Azure client update; Backend: ORDER BY SUM(pre_tax_cost) DESC LIMIT 10 |
| COST-06 | User can export cost breakdown data to CSV | Backend: FastAPI StreamingResponse with `text/csv` media type + Content-Disposition header; Frontend: download link triggering GET /costs/export |
</phase_requirements>

---

## Summary

Phase 3 delivers the main cost visibility dashboard. The backend provides six new API endpoints under `/costs` (spend summary, MoM comparison, daily trend, dimension breakdown, top resources, CSV export). The frontend replaces the DashboardPage placeholder with KPI cards, a time-series AreaChart, a breakdown table with dimension selector, and a top-10 table with CSV export button.

The most significant discovery is a **schema gap**: the current `billing_records` table stores `service_name`, `resource_group`, `subscription_id`, and `meter_category` — but not `region`, `tag`, `resource_id`, or `resource_name`. COST-04 (breakdown by region and tag) and COST-05 (top resources by resource name) require adding these columns via Alembic migration AND updating the Azure client's `QueryGrouping` and `_map_record` logic to capture them during ingestion.

The frontend stack already includes recharts (as a peer of the shadcn chart component), TanStack Query v5, axios, shadcn/ui, and Tailwind v4. No new npm packages are needed beyond adding the shadcn `chart`, `select`, `tabs`, and `table` components via the shadcn CLI.

**Primary recommendation:** Structure work as: (1) schema migration + Azure client + ingestion service update, (2) cost service layer + 6 API endpoints, (3) DashboardPage with KPI cards + trend chart, (4) breakdown + top-resources + export UI, (5) human verification checkpoint.

---

## Standard Stack

### Core (Backend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy async | 2.0+ (installed) | Aggregate queries: `func.sum`, `func.cast`, `group_by` | Already in project; async-native |
| FastAPI | 0.115+ (installed) | API endpoints + StreamingResponse CSV export | Already in project |
| Python csv + io.StringIO | stdlib | In-memory CSV generation, seek(0) before stream | No dependency; battle-tested pattern |
| Alembic | 1.13+ (installed) | Schema migration for new columns (region, tag, resource_id, resource_name) | Already in project |

### Core (Frontend)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| recharts | 2.x (shadcn dep) | AreaChart for daily trend, BarChart for breakdowns | shadcn chart is built on recharts; no lock-in |
| shadcn chart | via CLI | ChartContainer, ChartTooltip — themed chart wrapper | Matches project's shadcn/ui system exactly |
| shadcn tabs | via CLI | 30/60/90 day time range toggle | shadcn/ui — matches existing button/card style |
| shadcn select | via CLI | Dimension selector (service / resource_group / region / tag) | shadcn/ui — form-consistent |
| shadcn table | via CLI | Breakdown table + top-10 resources table | shadcn/ui — matches IngestionPage table pattern |
| TanStack Query | 5.x (installed) | Server state management, loading/error states | Already in project (package.json) |
| axios | 1.x (installed) | API calls via existing `api` singleton | Already in project — use `api.get(url, { responseType: 'blob' })` for CSV download |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| date-fns | (not installed) | Date arithmetic for projection formula | Skip — use native `Date` and `calendar` math; dependency not justified |
| pandas | (not installed) | CSV generation | Skip — Python `csv` module is sufficient for this data volume |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| shadcn chart (recharts) | Chart.js, Victory | recharts is shadcn's blessed chart library; existing ecosystem already includes it |
| Python csv + StringIO | pandas to_csv | pandas adds 30MB dependency; csv stdlib handles this fine |
| TanStack Query | useEffect + useState | TanStack Query already installed; provides caching, loading state, refetch |

### Installation (Frontend)

```bash
# Run from frontend/ directory (use npx, project uses shadcn v3.8.5)
npx shadcn@latest add chart
npx shadcn@latest add tabs
npx shadcn@latest add select
npx shadcn@latest add table
```

Note: recharts is installed automatically as a peer dependency of the chart component.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── models/billing.py          # ADD: region, tag, resource_id, resource_name columns
├── migrations/versions/       # NEW: Alembic migration for billing_records schema
├── schemas/cost.py            # NEW: Pydantic response schemas for cost endpoints
├── services/cost.py           # NEW: All aggregate query functions
└── api/v1/cost.py             # NEW: 6 endpoints registered in router.py

frontend/src/
├── pages/DashboardPage.tsx    # REPLACE placeholder with full dashboard
├── services/
│   └── cost.ts                # NEW: typed API functions for cost endpoints
└── components/
    └── ui/                    # chart.tsx, tabs.tsx, select.tsx, table.tsx (via shadcn CLI)
```

### Pattern 1: SQLAlchemy Async Aggregate Query

**What:** Use `select()` + `func.sum()` + `group_by()` + `await session.execute()` then `.all()` on the mapped result.
**When to use:** Any cost aggregation endpoint (daily trend, breakdown, top resources).

```python
# Source: SQLAlchemy 2.0 official docs https://docs.sqlalchemy.org/en/20/tutorial/data_select.html
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import BillingRecord

async def get_daily_spend(session: AsyncSession, days: int) -> list[tuple]:
    from datetime import date, timedelta
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            BillingRecord.usage_date,
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(BillingRecord.usage_date)
        .order_by(BillingRecord.usage_date)
    )
    result = await session.execute(stmt)
    return result.all()
```

**Key:** Use `result.all()` (not `.scalars().all()`) when the query returns multiple columns.

### Pattern 2: Month-to-Date Summary + Projection

**What:** Single endpoint returning MTD total + projected month-end + prior month for MoM.
**Formula:** `projection = (mtd_cost / days_elapsed) * days_in_month`

```python
# Source: standard linear extrapolation logic
from datetime import date
import calendar

def compute_projection(mtd_cost: float, today: date) -> float:
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day  # 1-indexed; day 1 = 1 day elapsed
    if days_elapsed == 0:
        return 0.0
    return (mtd_cost / days_elapsed) * days_in_month
```

### Pattern 3: shadcn ChartContainer + recharts AreaChart

**What:** shadcn `ChartContainer` wraps recharts `AreaChart`. Use CSS variables for theming. `min-h-[VALUE]` is required.
**When to use:** Daily spend trend visualization (COST-03).

```typescript
// Source: https://ui.shadcn.com/docs/components/radix/chart
import { Area, AreaChart, CartesianGrid, XAxis, YAxis, Tooltip } from "recharts";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import type { ChartConfig } from "@/components/ui/chart";

const chartConfig = {
  total_cost: {
    label: "Daily Spend",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

// data shape: [{ usage_date: "2026-01-15", total_cost: 245.50 }, ...]
export function SpendTrendChart({ data }: { data: DailySpend[] }) {
  return (
    <ChartContainer config={chartConfig} className="min-h-[300px] w-full">
      <AreaChart data={data}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="usage_date" tickLine={false} axisLine={false} />
        <YAxis tickFormatter={(v) => `$${v.toLocaleString()}`} />
        <ChartTooltip content={<ChartTooltipContent />} />
        <Area
          dataKey="total_cost"
          fill="var(--color-total_cost)"
          stroke="var(--color-total_cost)"
          fillOpacity={0.2}
        />
      </AreaChart>
    </ChartContainer>
  );
}
```

### Pattern 4: FastAPI CSV Export via StreamingResponse

**What:** Return CSV as a file download — no client-side library needed.
**When to use:** COST-06 export endpoint.

```python
# Source: https://fastapi.tiangolo.com/advanced/custom-response/
import csv
import io
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

@router.get("/costs/export")
async def export_costs(
    dimension: str = "service_name",
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = await get_breakdown(db, dimension=dimension, days=days)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["dimension", "total_cost", "currency"])
    for row in rows:
        writer.writerow([row.dimension_value, float(row.total_cost), "USD"])
    output.seek(0)  # CRITICAL: reset buffer position before streaming
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cost-breakdown.csv"},
    )
```

**Frontend download trigger:**

```typescript
// Use responseType: 'blob' to force binary download, then create object URL
const handleExport = async () => {
  const response = await api.get('/costs/export', {
    params: { dimension, days },
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', 'cost-breakdown.csv');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};
```

### Pattern 5: Pydantic Response Schemas for Aggregated Data

**What:** Return plain `BaseModel` schemas (not ORM models) from SQLAlchemy `Row` objects.
**When to use:** All cost endpoints — results are tuples from `result.all()`, not ORM instances.

```python
# Source: project pattern from schemas/ingestion.py
from pydantic import BaseModel
from decimal import Decimal

class DailySpendResponse(BaseModel):
    usage_date: str   # ISO date string, e.g. "2026-01-15"
    total_cost: Decimal

class BreakdownItemResponse(BaseModel):
    dimension_value: str
    total_cost: Decimal

class SpendSummaryResponse(BaseModel):
    mtd_total: Decimal
    projected_month_end: Decimal
    prior_month_total: Decimal
    mom_delta_pct: float   # percentage change, e.g. 12.5 = 12.5% increase

class TopResourceResponse(BaseModel):
    resource_id: str
    resource_name: str
    service_name: str
    resource_group: str
    total_cost: Decimal
```

**Note:** Do NOT use `model_config = {"from_attributes": True}` on these schemas — `result.all()` returns named tuples, not ORM objects. Map manually: `DailySpendResponse(usage_date=str(row.usage_date), total_cost=row.total_cost)`.

### Pattern 6: Dimension Breakdown Endpoint with Dynamic GROUP BY

**What:** Single endpoint accepts `?dimension=service_name|resource_group|region|tag` param and switches GROUP BY column.
**When to use:** COST-04.

```python
DIMENSION_MAP = {
    "service_name": BillingRecord.service_name,
    "resource_group": BillingRecord.resource_group,
    "region": BillingRecord.region,           # requires new column
    "tag": BillingRecord.tag,                 # requires new column
}

async def get_breakdown(
    session: AsyncSession,
    dimension: str,
    days: int,
) -> list:
    col = DIMENSION_MAP.get(dimension)
    if col is None:
        raise ValueError(f"Invalid dimension: {dimension}")
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(col.label("dimension_value"), func.sum(BillingRecord.pre_tax_cost).label("total_cost"))
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(col)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
    )
    result = await session.execute(stmt)
    return result.all()
```

### Anti-Patterns to Avoid

- **Using `.scalars().all()` for multi-column aggregate queries:** `.scalars()` only returns the first column. Use `result.all()` when the query selects multiple columns.
- **Calling `output.seek(0)` before writing CSV:** Seek must happen AFTER writing. Call `output.seek(0)` after all `writer.writerow()` calls, before passing to `StreamingResponse`.
- **Module-level `get_settings()` in cost service:** Follow established project pattern — call `get_settings()` at function-call time, not module level (required for test cache invalidation, see STATE.md decision).
- **Blocking the event loop with synchronous CSV generation:** The Python `csv` module is synchronous but writes to in-memory StringIO — no I/O blocking, safe to call directly in async endpoints.
- **Forgetting `min-h-[VALUE]` on ChartContainer:** Without this, the chart renders with zero height and is invisible. This is a required prop.
- **Using `useEffect` polling for cost data:** Unlike IngestionPage status, cost data doesn't change during a user session. Use TanStack Query's standard `useQuery` — it handles loading/error states and doesn't poll by default.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chart rendering | Custom SVG charts | recharts AreaChart/BarChart via shadcn chart | Animation, tooltips, responsiveness have dozens of edge cases |
| CSV string generation | Manual string concatenation | Python `csv.writer` + `io.StringIO` | Handles quoting, escaping, delimiter edge cases |
| Date range buttons | Custom toggle component | shadcn `Tabs` or shadcn `Button` group | Already styled to match UI system |
| Responsive chart sizing | Custom ResizeObserver | recharts `ResponsiveContainer` (used internally by shadcn ChartContainer) | Already handled by ChartContainer |
| Month-end projection | Complex forecasting | Linear extrapolation: `(mtd / days_elapsed) * days_in_month` | Sufficient for MVP; no ML needed |

**Key insight:** The cost domain's main complexity is in the SQL aggregation layer, not the UI rendering. Use library primitives everywhere and keep custom logic to the service layer only.

---

## Critical Schema Gap (Action Required in Plan 1)

The `billing_records` table is **missing four columns** required by COST-04 and COST-05:

| Missing Column | Required For | Type | Source in Azure API |
|----------------|-------------|------|---------------------|
| `region` | COST-04 breakdown by region | `String(100)` | `QueryGrouping(type=DIMENSION, name="ResourceLocation")` |
| `tag` | COST-04 breakdown by tag | `String(500)` | `QueryGrouping(type=TAG, name="tenant_id")` (or general tag column) |
| `resource_id` | COST-05 top resources | `String(500)` | `QueryGrouping(type=DIMENSION, name="ResourceId")` |
| `resource_name` | COST-05 top resources display | `String(500)` | Derived from `ResourceId` or separate grouping |

**Migration plan:** New Alembic migration adding these columns with `nullable=True, default=""` to preserve existing data. Update `BillingRecord` model, unique constraint key (if resource_id is needed in it), `_map_record()` mapping function, and `QueryGrouping` list in the Azure client.

**Note on tag:** The Azure Cost Management API returns tag data differently from dimensions — you specify `QueryGrouping(type=QueryColumnType.TAG, name="tagname")`. For a general "tag" column, storing the raw tag key-value string (e.g., `"env:prod"`) is sufficient for MVP breakdown display. The `tenant_id` tag used in Phase 6 attribution is a future concern.

**Note on unique constraint:** Adding `resource_id` to the unique constraint key is needed if we want per-resource granularity in upsert deduplication. However, the existing unique constraint `(usage_date, subscription_id, resource_group, service_name, meter_category)` may conflict with per-resource granularity. Plan should address this: the safe MVP approach is to add region/tag/resource columns as supplementary data, keep the existing unique key, and accept that top-resource queries group by `service_name + resource_group` as a proxy for resource identity unless `resource_id` is added to the key.

---

## Common Pitfalls

### Pitfall 1: Empty Charts When Data Has Gaps

**What goes wrong:** The daily trend chart shows breaks or renders incorrectly when there are days with no billing records (weekends, Azure delay in data availability).
**Why it happens:** recharts AreaChart renders null/undefined data points as gaps, not zero.
**How to avoid:** In the service layer, generate a complete date series and left-join or fill missing dates with 0.0 cost. Alternatively, pass `connectNulls={true}` to the `<Area>` component to connect across gaps.
**Warning signs:** Chart line breaks on weekends or early in the month.

### Pitfall 2: Decimal Serialization Mismatch

**What goes wrong:** FastAPI serializes `Decimal` fields as strings in JSON by default, breaking frontend `parseFloat()`.
**Why it happens:** `Numeric(18, 6)` columns return Python `Decimal` objects; FastAPI default JSON encoder doesn't handle Decimal → number.
**How to avoid:** Use `float` in Pydantic response schemas (`total_cost: float`) OR configure FastAPI JSON encoder. The simplest approach: cast `Decimal` to `float` when constructing response objects: `total_cost=float(row.total_cost)`.
**Warning signs:** Frontend receives `"245.500000"` (string) instead of `245.5` (number), causing chart to not render.

### Pitfall 3: CSV Download Opens in Browser Instead of Downloading

**What goes wrong:** Browser renders CSV as text instead of triggering file download.
**Why it happens:** Missing or incorrect `Content-Disposition` header.
**How to avoid:** Always include `Content-Disposition: attachment; filename=filename.csv` header in `StreamingResponse`. On frontend, use `responseType: 'blob'` in axios and create an object URL.
**Warning signs:** Browser tab shows CSV text content instead of download dialog.

### Pitfall 4: MoM Delta Division by Zero

**What goes wrong:** Server error when prior month has zero spend (e.g., first month of operation).
**Why it happens:** Dividing by zero in `(current - prior) / prior * 100` percentage formula.
**How to avoid:** Guard: if `prior_month_total == 0`, return `mom_delta_pct = None` or `0.0` with a flag. Frontend should handle null delta gracefully (show "N/A" or "First period").
**Warning signs:** 500 error on summary endpoint during first month.

### Pitfall 5: Tag Column in Azure API Returns Empty for Untagged Resources

**What goes wrong:** Most billing records have no tag, resulting in a tag breakdown that shows only one item (the single tagged resource group).
**Why it happens:** Many Azure resources are not tagged with `tenant_id` at MVP stage.
**How to avoid:** Tag breakdown is still valuable for Phase 6 attribution setup. Display it with an "Untagged" bucket for resources missing the tag value. Filter out empty-string tag values from the breakdown display, or group them as "Untagged".
**Warning signs:** Tag breakdown shows one row with a huge percentage of total cost labeled as empty string.

### Pitfall 6: Forgetting to Add New Endpoint to router.py

**What goes wrong:** All cost endpoints return 404.
**Why it happens:** FastAPI requires explicit router inclusion in `app/api/v1/router.py`.
**How to avoid:** After creating `api/v1/cost.py`, add `from app.api.v1 import cost` and `api_router.include_router(cost.router)` in `router.py`.
**Warning signs:** All cost API calls return 404 Not Found.

### Pitfall 7: shadcn Chart Component Not Found After CLI Add

**What goes wrong:** TypeScript error: `Cannot find module '@/components/ui/chart'`.
**Why it happens:** shadcn CLI places file at `src/components/ui/chart.tsx` — if tsconfig paths alias `@/` points elsewhere, the import fails.
**How to avoid:** After running `npx shadcn@latest add chart`, verify `src/components/ui/chart.tsx` exists. The project already has the `@/` alias configured (used by existing components).
**Warning signs:** TypeScript compilation fails with module not found on chart import.

---

## Code Examples

### Daily Spend Aggregation (Backend)

```python
# Source: SQLAlchemy 2.0 docs + project ingestion.py patterns
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.billing import BillingRecord
from datetime import date, timedelta

async def get_daily_spend(session: AsyncSession, days: int) -> list:
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            BillingRecord.usage_date,
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(BillingRecord.usage_date)
        .order_by(BillingRecord.usage_date)
    )
    result = await session.execute(stmt)
    return result.all()
    # Access rows: row.usage_date, row.total_cost
```

### MTD + Projection Query (Backend)

```python
# Source: standard SQLAlchemy + stdlib calendar
from sqlalchemy import select, func, extract
from datetime import date
import calendar

async def get_spend_summary(session: AsyncSession) -> dict:
    today = date.today()
    # Month-to-date
    mtd_stmt = (
        select(func.sum(BillingRecord.pre_tax_cost).label("total"))
        .where(
            extract("year", BillingRecord.usage_date) == today.year,
            extract("month", BillingRecord.usage_date) == today.month,
        )
    )
    mtd_result = await session.execute(mtd_stmt)
    mtd_total = float(mtd_result.scalar() or 0.0)

    # Prior month
    if today.month == 1:
        prior_year, prior_month = today.year - 1, 12
    else:
        prior_year, prior_month = today.year, today.month - 1

    prior_stmt = (
        select(func.sum(BillingRecord.pre_tax_cost).label("total"))
        .where(
            extract("year", BillingRecord.usage_date) == prior_year,
            extract("month", BillingRecord.usage_date) == prior_month,
        )
    )
    prior_result = await session.execute(prior_stmt)
    prior_total = float(prior_result.scalar() or 0.0)

    # Projection
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    projection = (mtd_total / days_elapsed * days_in_month) if days_elapsed > 0 else 0.0

    # MoM delta
    mom_delta = ((mtd_total - prior_total) / prior_total * 100) if prior_total > 0 else None

    return {
        "mtd_total": mtd_total,
        "projected_month_end": projection,
        "prior_month_total": prior_total,
        "mom_delta_pct": mom_delta,
    }
```

### Alembic Migration for New Columns (Backend)

```python
# Source: project pattern from 55bda49dc4a2_billing_ingestion_tables.py
def upgrade() -> None:
    op.add_column("billing_records", sa.Column("region", sa.String(100), nullable=False, server_default=""))
    op.add_column("billing_records", sa.Column("tag", sa.String(500), nullable=False, server_default=""))
    op.add_column("billing_records", sa.Column("resource_id", sa.String(500), nullable=False, server_default=""))
    op.add_column("billing_records", sa.Column("resource_name", sa.String(500), nullable=False, server_default=""))
    op.create_index("idx_billing_region", "billing_records", ["region"])

def downgrade() -> None:
    op.drop_index("idx_billing_region", "billing_records")
    op.drop_column("billing_records", "resource_name")
    op.drop_column("billing_records", "resource_id")
    op.drop_column("billing_records", "tag")
    op.drop_column("billing_records", "region")
```

### Cost API Router (Backend)

```python
# Source: project pattern from api/v1/ingestion.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.cost import SpendSummaryResponse, DailySpendResponse, BreakdownItemResponse
from app.services.cost import get_spend_summary, get_daily_spend, get_breakdown, get_top_resources

router = APIRouter(prefix="/costs", tags=["costs"])

@router.get("/summary", response_model=SpendSummaryResponse)
async def spend_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return await get_spend_summary(db)

@router.get("/trend", response_model=list[DailySpendResponse])
async def spend_trend(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = await get_daily_spend(db, days=days)
    return [DailySpendResponse(usage_date=str(r.usage_date), total_cost=float(r.total_cost)) for r in rows]

@router.get("/breakdown", response_model=list[BreakdownItemResponse])
async def spend_breakdown(
    dimension: str = Query(default="service_name", pattern="^(service_name|resource_group|region|tag)$"),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    rows = await get_breakdown(db, dimension=dimension, days=days)
    return [BreakdownItemResponse(dimension_value=r.dimension_value, total_cost=float(r.total_cost)) for r in rows]
```

### TanStack Query for Cost Data (Frontend)

```typescript
// Source: TanStack Query v5 docs + project api.ts pattern
import { useQuery } from '@tanstack/react-query';
import api from '@/services/api';

interface SpendSummary {
  mtd_total: number;
  projected_month_end: number;
  prior_month_total: number;
  mom_delta_pct: number | null;
}

export function useSpendSummary() {
  return useQuery<SpendSummary>({
    queryKey: ['spend-summary'],
    queryFn: async () => {
      const { data } = await api.get<SpendSummary>('/costs/summary');
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes — cost data doesn't change mid-session
  });
}

export function useSpendTrend(days: number) {
  return useQuery({
    queryKey: ['spend-trend', days],
    queryFn: async () => {
      const { data } = await api.get('/costs/trend', { params: { days } });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Manual chart sizing with fixed pixel widths | `ChartContainer` with `min-h-[VALUE] w-full` — ResponsiveContainer under the hood | Charts resize correctly on all viewports |
| `recharts` v2 direct usage | shadcn `chart` component wrapping recharts | Automatic CSS variable theming, dark mode, consistent tooltip style |
| pandas for CSV export | Python stdlib `csv` + `io.StringIO` | No extra dependency; sufficient for this data volume |
| TanStack Query v4 `useQuery` options | TanStack Query v5: `queryKey` + `queryFn` in single object, no separate `options` arg | v5 is installed; use v5 API pattern |

**Deprecated/outdated patterns:**
- `recharts` `<ResponsiveContainer>` used directly: shadcn `ChartContainer` handles this internally — don't add `ResponsiveContainer` yourself when using shadcn chart.
- TanStack Query v4 `useQuery(key, fn, options)` three-arg form: use v5 single-object form `useQuery({ queryKey, queryFn })`.

---

## Open Questions

1. **Tag column granularity for COST-04**
   - What we know: Azure API supports tag grouping via `QueryGrouping(type=QueryColumnType.TAG, name="tagname")`. Tags are returned as a string column value.
   - What's unclear: Should we store one specific tag (e.g., `tenant_id`) or a general "tag" column? For Phase 6, `tenant_id` is the key tag. For COST-04 display, any tag breakdown is acceptable.
   - Recommendation: Store `tag` as the `tenant_id` tag value (empty string if absent). This satisfies COST-04 and pre-seeds Phase 6 attribution. Column name: `tag`, value: the raw `tenant_id` tag value string.

2. **Unique constraint key with resource_id**
   - What we know: Current unique key is `(usage_date, subscription_id, resource_group, service_name, meter_category)`. Adding `resource_id` would enable per-resource granularity but change upsert behavior.
   - What's unclear: Whether Azure's response returns distinct resource_ids for the current grouping, or whether resource_id data would break existing duplicate detection.
   - Recommendation: Do NOT add `resource_id` to the unique constraint for Phase 3. Add it as a non-key column. Top-10 resource query can group by `(resource_id, service_name, resource_group)` without affecting upsert semantics.

3. **MoM comparison: full prior month vs. same-period prior month**
   - What we know: COST-02 says "compare current period spend to previous period (MoM)".
   - What's unclear: Full prior month total vs. prior-month-to-same-day (apples-to-apples comparison).
   - Recommendation: Show full prior month total with clear labeling. It's simpler and more useful for finance review. Include prior month name in the response label.

---

## Sources

### Primary (HIGH confidence)

- Official SQLAlchemy 2.0 docs — https://docs.sqlalchemy.org/en/20/tutorial/data_select.html — aggregate query patterns
- Official FastAPI docs — https://fastapi.tiangolo.com/advanced/custom-response/ — StreamingResponse CSV export
- Official shadcn/ui chart docs — https://ui.shadcn.com/docs/components/radix/chart — ChartContainer, ChartConfig, installation
- Project source: `backend/app/models/billing.py` — confirmed BillingRecord schema (no region/tag/resource columns)
- Project source: `backend/app/services/azure_client.py` — confirmed current QueryGrouping (no ResourceLocation/TAG)
- Project source: `backend/app/api/v1/ingestion.py` — API endpoint pattern to follow
- Project source: `frontend/package.json` — confirmed TanStack Query v5, axios, shadcn v3.8.5 installed

### Secondary (MEDIUM confidence)

- Azure Cost Management REST API docs — https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage — ResourceLocation and TAG dimensions available
- WebSearch on shadcn chart 2026 — confirmed recharts v2 is current stable, v3 upgrade in progress (use v2 patterns)
- WebSearch on CSV StreamingResponse — confirmed seek(0) + Content-Disposition pattern

### Tertiary (LOW confidence)

- recharts BarChart/AreaChart API specifics — based on WebSearch results + shadcn docs; validate against installed recharts version after `npx shadcn@latest add chart`

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed via package.json, project source files, official docs
- Schema gap finding: HIGH — confirmed by reading billing.py and azure_client.py directly
- Architecture patterns: HIGH — based on existing project API/service/schema patterns
- SQLAlchemy aggregate query syntax: HIGH — verified with official SQLAlchemy 2.0 docs
- shadcn chart usage: HIGH — verified with official shadcn/ui docs
- CSV export pattern: HIGH — verified with FastAPI official docs
- Tag column behavior in Azure API: MEDIUM — based on Azure docs + known issues in GitHub

**Research date:** 2026-02-20
**Valid until:** 2026-03-22 (30 days — stable libraries, but check shadcn recharts v3 upgrade status)
