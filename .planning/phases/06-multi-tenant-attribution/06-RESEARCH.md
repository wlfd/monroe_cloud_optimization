# Phase 6: Multi-Tenant Attribution - Research

**Researched:** 2026-02-21
**Domain:** Tag-based cost attribution, allocation rule engine, per-tenant reporting, Settings UI
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Tenant Discovery**
- Tenants are auto-discovered from distinct `tenant_id` tag values seen in Azure resource data — no pre-registration required
- Admin can optionally assign a human-readable display name to each discovered tenant ID
- When a new `tenant_id` tag appears for the first time, flag it visually in the UI with a "New" badge until admin acknowledges it
- Untagged resources: allocation rules apply first; any cost not covered by a rule appears as a separate "Unallocated" bucket

**Tenant Management (Settings)**
- A dedicated Settings/Admin page hosts tenant name management (separate from the attribution view)
- The same Settings page also houses allocation rule management — use tabs or sections to separate the two

**Per-Tenant Attribution View**
- Sortable table layout — one row per tenant, dense and scannable
- Each row shows: tenant name/ID, monthly cost ($), % of total spend, month-over-month change ($ or %), top resource category
- Time range defaults to current month; user can navigate back to previous months via a month picker
- Clicking a row expands it inline to show a cost breakdown by service category for that tenant

**Allocation Rule Management**
- Rules table with inline Add Rule form (clicking "Add Rule" opens an inline row for input, not a modal)
- A rule can target either a resource group (by name) or a service category (e.g., Compute, Storage) — both target types supported
- When multiple rules match the same resource, first rule wins based on admin-defined priority order
- Rules live on the same Settings page as tenant names

### Claude's Discretion
- Exact column widths, sorting defaults, and table styling
- Badge design and acknowledgement mechanic for new tenants
- How priority ordering is visually managed in the rules table (drag-and-drop vs. numbered input)
- Compression algorithm and temp file handling for CSV export

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.

**Specific implementation notes from CONTEXT.md:**
- The "Unallocated" bucket should appear as its own row in the tenant attribution table so finance can see how much spend hasn't been attributed yet
- The Settings page tenant and rules sections should feel cohesive — admin shouldn't need to navigate between multiple pages to configure attribution
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ATTR-01 | System maps Azure resources to tenants via `tenant_id` resource tag on a daily schedule | BillingRecord.tag column already stores tenant_id value (empty string for untagged). Daily attribution run reads DISTINCT tag values → derives TenantProfile rows. Scheduled via existing APScheduler lifespan pattern. |
| ATTR-02 | Admin can define shared/untagged resource allocation rules (by-tenant-count, by-usage, or manual percentage splits) | AllocationRule model with method enum (by_count, by_usage, manual_pct), target_type (resource_group, service_category), JSON percentages column. Apply rules at attribution-run time to distribute untagged costs. |
| ATTR-03 | User can view monthly infrastructure cost per tenant | TenantAttribution table stores pre-computed monthly totals per tenant_id per month. FastAPI /attribution endpoint returns list ordered by cost. Frontend AttributionPage with shadcn Table (already installed). |
| ATTR-04 | User can export per-tenant cost report to CSV | StreamingResponse CSV pattern already established in cost.py and anomaly.py. Export endpoint at GET /attribution/export with year/month params. Frontend blob download pattern already proven in Phase 3. |
</phase_requirements>

---

## Summary

Phase 6 builds on the data foundation established in Phase 2 (data ingestion) and Phase 3 (cost monitoring). The critical insight is that `BillingRecord.tag` already stores raw `tenant_id` tag values (empty string for untagged) — this was explicitly seeded in Phase 3 as a forward-looking decision. No new Azure API calls are needed; all attribution logic reads from the existing `billing_records` table.

The architecture has three distinct data concerns: (1) a `tenant_profiles` table that maps raw tag strings to display names and tracks "new" status, (2) an `allocation_rules` table that defines how untagged/shared resources are split, and (3) a `tenant_attributions` table that stores pre-computed monthly cost totals per tenant. The daily attribution job runs after ingestion to refresh these pre-computed rows. Pre-computation is essential — computing attribution on-the-fly across 30 tenants with three split methods would be slow and non-deterministic.

The frontend has two distinct surfaces: the Attribution page (sortable table with expandable rows, month picker) and the Settings page (tabbed: tenant names + allocation rules). Both `/attribution` and `/settings` routes are already stubbed in the sidebar (`AppSidebar.tsx` already includes `{ title: 'Attribution', url: '/attribution' }` and `{ title: 'Settings', url: '/settings' }`), and the App.tsx router has placeholder comments for these routes. No shadcn components need installation — `table.tsx`, `tabs.tsx`, `badge.tsx`, `select.tsx`, `button.tsx`, `input.tsx`, `card.tsx`, and `skeleton.tsx` are all already installed.

**Primary recommendation:** Store attribution as pre-computed monthly snapshots in `tenant_attributions` (updated by daily job), not computed on-the-fly. This makes the /attribution query a simple SELECT with no aggregation math at request time.

---

## Standard Stack

### Core — No New Dependencies Needed

All required libraries are already installed. Phase 6 adds no new npm packages and no new Python packages.

| Layer | Technology | Version | Already Installed |
|-------|------------|---------|-------------------|
| Backend ORM | SQLAlchemy (async) | >=2.0 | Yes |
| Backend API | FastAPI | >=0.115 | Yes |
| Backend scheduler | APScheduler | 3.11.2 | Yes |
| DB migrations | Alembic | >=1.13 | Yes |
| Frontend query | TanStack Query | ^5.90.21 | Yes |
| Frontend HTTP | Axios | ^1.13.5 | Yes |
| Frontend UI | shadcn/ui components | latest | Yes (table, tabs, badge, select, button, input, card, skeleton) |
| Frontend routing | react-router-dom | ^7.13.0 | Yes |

### Supporting

| Tool | Purpose | Notes |
|------|---------|-------|
| `csv` (Python stdlib) | CSV export | Already used in cost.py and anomaly.py |
| `io.StringIO` (Python stdlib) | CSV streaming buffer | Already used in cost.py and anomaly.py |
| `uuid4` (Python stdlib) | Primary keys | Already used in all models |

### Alternatives Considered

| Instead of | Could Use | Why Not |
|------------|-----------|---------|
| Pre-computed monthly snapshot table | On-the-fly SQL aggregation with three split methods | On-the-fly computation is non-deterministic across rule changes; snapshots are fast, auditable, and deterministic |
| APScheduler daily cron job (existing pattern) | Celery + Redis task queue | APScheduler already embedded; no additional infrastructure needed |
| JSON column for manual_pct allocations | Separate allocation_rule_tenants join table | JSON is simpler for a dict of {tenant_id: pct}; 30 tenants fits trivially |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/app/
├── models/
│   └── attribution.py          # TenantProfile, AllocationRule, TenantAttribution models
├── schemas/
│   └── attribution.py          # Pydantic response/request schemas
├── services/
│   └── attribution.py          # Daily attribution job + CRUD helpers
├── api/v1/
│   ├── attribution.py          # FastAPI router: GET /attribution, /attribution/export, /attribution/breakdown/{tenant_id}
│   └── settings.py             # FastAPI router: tenant CRUD, rule CRUD
│   └── router.py               # Updated to include new routers
├── migrations/versions/
│   └── {hash}_add_attribution_tables.py

frontend/src/
├── pages/
│   ├── AttributionPage.tsx     # Sortable table + month picker + expandable rows
│   └── SettingsPage.tsx        # Tabs: Tenant Names | Allocation Rules
├── services/
│   └── attribution.ts          # TanStack Query hooks + mutation hooks + exportAttribution()
└── App.tsx                     # Uncomment /attribution and /settings routes
```

### Pattern 1: Pre-Computed Monthly Attribution Snapshots

**What:** A daily job reads all billing_records for the current month, applies allocation rules to untagged/shared costs, then UPSERTS one row per (tenant_id, year, month) into `tenant_attributions`. On conflict updates cost figures.

**When to use:** Any time attribution totals are needed in the UI. The UI query is a simple `SELECT * FROM tenant_attributions WHERE year=? AND month=?` — no runtime math.

**Example (SQLAlchemy upsert pattern already proven in ingestion.py):**
```python
# Source: established pattern from app/services/ingestion.py (pg_insert upsert)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.attribution import TenantAttribution

stmt = pg_insert(TenantAttribution).values(rows_to_upsert)
stmt = stmt.on_conflict_do_update(
    index_elements=["tenant_id", "year", "month"],
    set_={
        "total_cost": stmt.excluded.total_cost,
        "pct_of_total": stmt.excluded.pct_of_total,
        "mom_delta_usd": stmt.excluded.mom_delta_usd,
        "top_service_category": stmt.excluded.top_service_category,
        "updated_at": stmt.excluded.updated_at,
    }
)
await session.execute(stmt)
await session.commit()
```

### Pattern 2: Three Allocation Methods

**What:** When applying allocation rules to untagged/shared resources, three split methods are supported:

| Method | How It Works | When Admin Uses It |
|--------|-------------|-------------------|
| `by_count` | Divide untagged cost evenly across all known tenants | Default — fair split, no usage data needed |
| `by_usage` | Divide proportionally by each tenant's tagged cost that month | More accurate — reflects actual usage ratio |
| `manual_pct` | Admin provides explicit percentages per tenant (must sum to 100) | Fixed contractual splits, e.g., tenant A=60%, B=40% |

**Example (attribution service logic):**
```python
# Source: original — based on standard cost allocation patterns
def apply_rule(untagged_cost: float, method: str, manual_pct: dict,
               tenant_costs: dict[str, float]) -> dict[str, float]:
    """Returns {tenant_id: allocated_amount} dict."""
    if method == "by_count":
        per_tenant = untagged_cost / len(tenant_costs)
        return {t: per_tenant for t in tenant_costs}
    elif method == "by_usage":
        total_tagged = sum(tenant_costs.values())
        if total_tagged == 0:
            # Fallback to by_count if no tagged usage yet
            per_tenant = untagged_cost / len(tenant_costs)
            return {t: per_tenant for t in tenant_costs}
        return {t: untagged_cost * (cost / total_tagged)
                for t, cost in tenant_costs.items()}
    elif method == "manual_pct":
        return {t: untagged_cost * (pct / 100.0)
                for t, pct in manual_pct.items()}
```

### Pattern 3: Scheduled Attribution Job (APScheduler CronTrigger — existing pattern)

**What:** Register a daily CronTrigger job in main.py lifespan that calls `run_attribution()`. Same pattern as the existing recommendation daily job.

**When to use:** ATTR-01 requires automatic daily mapping without manual steps.

**Example (following main.py pattern exactly):**
```python
# Source: established pattern from app/main.py (recommendation daily job)
from app.services.attribution import run_attribution

async def _scheduled_attribution():
    await run_attribution()

scheduler.add_job(
    _scheduled_attribution,
    CronTrigger(hour=3, minute=0, timezone="UTC"),  # After ingestion (4h) and recommendations (02:00)
    id="attribution_daily",
    replace_existing=True,
)
```

### Pattern 4: Tenant Discovery from BillingRecord.tag

**What:** Each daily attribution run performs `SELECT DISTINCT tag FROM billing_records WHERE tag != ''` to discover all known tenant IDs. For each discovered ID, UPSERT a row into `tenant_profiles` — set `is_new=True` on first insert, leave it unchanged on subsequent upserts. Admin acknowledges by calling `PATCH /settings/tenants/{tenant_id}/acknowledge`.

```python
# Source: established pattern from ingestion.py (pg_insert upsert)
from sqlalchemy import select, distinct
from app.models.billing import BillingRecord

stmt = select(distinct(BillingRecord.tag)).where(BillingRecord.tag != "")
result = await session.execute(stmt)
discovered_ids = [row[0] for row in result.all()]
```

### Pattern 5: Expandable Table Row (Frontend)

**What:** Attribution table uses `useState<string | null>(expandedTenantId)`. Clicking a row sets the expanded ID. An extra `<tr>` immediately following the clicked row renders the service-category breakdown for that tenant (fetched via a secondary query hook). The shadcn `Table` component is already installed.

**When to use:** CONTEXT.md decision: "clicking a row expands it inline."

```typescript
// Source: established shadcn Table pattern from frontend/src/components/ui/table.tsx
const [expandedId, setExpandedId] = useState<string | null>(null);

function handleRowClick(tenantId: string) {
  setExpandedId(prev => prev === tenantId ? null : tenantId);
}

// In JSX:
<TableRow
  key={tenant.tenant_id}
  className="cursor-pointer hover:bg-muted/50"
  onClick={() => handleRowClick(tenant.tenant_id)}
>
  ...cells...
</TableRow>
{expandedId === tenant.tenant_id && (
  <TableRow>
    <TableCell colSpan={6} className="bg-muted/20 p-0">
      <TenantBreakdown tenantId={tenant.tenant_id} yearMonth={yearMonth} />
    </TableCell>
  </TableRow>
)}
```

### Pattern 6: Month Picker (No New Components Needed)

**What:** A month picker can be built with two shadcn `Select` components (one for month, one for year) rather than a calendar date picker. CONTEXT.md says "user can navigate back to previous months." Keep it simple — no date picker library needed.

```typescript
// Month/year state derived into year: number, month: number
const [year, setYear] = useState(new Date().getFullYear());
const [month, setMonth] = useState(new Date().getMonth() + 1);  // 1-indexed

// Query key changes on year/month change → TanStack Query refetches
const { data } = useAttribution(year, month);
```

### Pattern 7: Inline Add Rule Form

**What:** The rules table has an "Add Rule" button. Clicking it appends a special editing row (controlled by `isAddingRule` state). On save, the row calls `POST /settings/rules`. This avoids a modal and keeps the UI within the table context as decided.

```typescript
const [isAddingRule, setIsAddingRule] = useState(false);
const [newRule, setNewRule] = useState<Partial<AllocationRule>>({});

// In table JSX — append after existing rows:
{isAddingRule && (
  <TableRow>
    <TableCell><Input value={newRule.target_value} onChange={...} /></TableCell>
    <TableCell><Select ... /></TableCell>
    <TableCell>
      <Button size="sm" onClick={handleSaveRule}>Save</Button>
      <Button size="sm" variant="ghost" onClick={() => setIsAddingRule(false)}>Cancel</Button>
    </TableCell>
  </TableRow>
)}
```

### Anti-Patterns to Avoid

- **Computing attribution on-the-fly in the GET /attribution request handler:** Makes each API call O(N billing records * M rules). Pre-compute in the daily job instead.
- **Storing `manual_pct` as separate table rows:** A JSON column `{tenant_id: pct}` is sufficient for 30 tenants and avoids a join.
- **Installing a date picker library for the month picker:** Two shadcn Select components (month, year) fully satisfy the requirement without adding a dependency.
- **Ignoring the `tag` column already containing tenant_id:** Phase 3 deliberately stored raw `tenant_id` tag value there. Attribution does not need a new column or new Azure API query.
- **Allowing overlapping rules without priority:** First-rule-wins (by `priority` integer) is the locked decision. Enforce this in service layer, not the DB.
- **Invalidating all TanStack Query keys on settings mutations:** Scope invalidation to `['attribution']` and `['tenants']` separately to avoid unnecessary re-fetches.

---

## Data Models

### Backend Models (`app/models/attribution.py`)

```python
# Three new SQLAlchemy models needed:

class TenantProfile(Base):
    """One row per distinct tenant_id tag value ever seen."""
    __tablename__ = "tenant_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)  # raw tag value
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # admin-set
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)  # "New" badge flag
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AllocationRule(Base):
    """Admin-defined rules for distributing untagged/shared resource costs."""
    __tablename__ = "allocation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)  # first-rule-wins ordering
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'resource_group' | 'service_category'
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "rg-shared" or "Compute"
    method: Mapped[str] = mapped_column(String(50), nullable=False)  # 'by_count' | 'by_usage' | 'manual_pct'
    manual_pct: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # {tenant_id: pct} only for manual_pct
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("priority", name="uq_allocation_rule_priority"),
    )


class TenantAttribution(Base):
    """Pre-computed monthly cost totals per tenant. Updated by daily attribution job."""
    __tablename__ = "tenant_attributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)  # 'UNALLOCATED' for unmatched costs
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    mom_delta_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)  # None if no prior month
    top_service_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    allocated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)  # from rules
    tagged_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)   # directly tagged
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", name="uq_tenant_attribution_key"),
        Index("idx_attribution_year_month", "year", "month"),
        Index("idx_attribution_tenant_id", "tenant_id"),
    )
```

**JSON column note:** SQLAlchemy supports `JSON` column type natively. Import: `from sqlalchemy import JSON`. This works with PostgreSQL's `jsonb` type. Confidence: HIGH (SQLAlchemy docs).

### Tenant Attribution Service Layer

The `attribution.py` service needs these functions:

| Function | Purpose |
|----------|---------|
| `run_attribution()` | Daily job: discover tenants, apply rules, upsert TenantAttribution |
| `get_attributions(session, year, month)` | Return list of TenantAttribution rows for month |
| `get_attribution_breakdown(session, tenant_id, year, month)` | Return per-service-category breakdown for one tenant/month |
| `list_tenant_profiles(session)` | All TenantProfile rows |
| `update_tenant_display_name(session, tenant_id, name)` | Admin rename |
| `acknowledge_tenant(session, tenant_id)` | Clear is_new flag |
| `list_allocation_rules(session)` | All rules ordered by priority |
| `create_allocation_rule(session, rule_data)` | Insert new rule |
| `update_allocation_rule(session, rule_id, rule_data)` | Update rule |
| `delete_allocation_rule(session, rule_id)` | Remove rule |

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSV streaming | Custom byte-level file builder | `csv.writer` + `io.StringIO` + `StreamingResponse` (already used in cost.py) | Handles quoting, encoding, RFC compliance |
| Upsert-or-insert for monthly snapshot | Manual SELECT + INSERT/UPDATE | `pg_insert(...).on_conflict_do_update(...)` (already used in ingestion.py) | Atomic, race-condition-safe |
| Client-side sorting | Custom sort function | shadcn Table with `useState<{key, dir}>` controlling a `.sort()` on the data array | Trivial for 30 rows; server-side sort overkill |
| Month arithmetic for MoM delta | Custom date math | Python `calendar.monthrange` + conditional prior-month query (already used in cost.py) | Already proven, handles January→December edge case |
| Percentage validation for manual_pct | Custom validator | Pydantic `@model_validator` on the schema, check `sum(pct.values()) == 100` | Pydantic already in use; validator runs on POST/PUT |

**Key insight:** Every hard problem in this phase (upsert, CSV streaming, MoM deltas, date math) has already been solved in earlier phases. Follow the existing patterns exactly.

---

## API Endpoints

### Attribution Router (`/api/v1/attribution`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/attribution/` | user | List TenantAttribution rows for year/month |
| GET | `/attribution/breakdown/{tenant_id}` | user | Per-service breakdown for one tenant/month |
| GET | `/attribution/export` | user | CSV export of attribution for year/month |
| POST | `/attribution/run` | admin | Trigger attribution job manually |

### Settings Router (`/api/v1/settings`)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/settings/tenants` | admin | List all TenantProfile rows |
| PATCH | `/settings/tenants/{tenant_id}/name` | admin | Update display name |
| POST | `/settings/tenants/{tenant_id}/acknowledge` | admin | Clear is_new flag |
| GET | `/settings/rules` | admin | List AllocationRule rows ordered by priority |
| POST | `/settings/rules` | admin | Create new rule |
| PATCH | `/settings/rules/{rule_id}` | admin | Update rule |
| DELETE | `/settings/rules/{rule_id}` | admin | Delete rule |
| POST | `/settings/rules/reorder` | admin | Update priority ordering (accepts ordered list of IDs) |

---

## Common Pitfalls

### Pitfall 1: The UNALLOCATED Row Sentinel Value

**What goes wrong:** When no allocation rule matches an untagged resource, the remaining cost has no tenant to attribute to. If this is silently dropped, finance can't detect attribution gaps.

**Why it happens:** Code only distributes costs that match a rule, discarding the rest.

**How to avoid:** Reserve `tenant_id = 'UNALLOCATED'` as a sentinel. After applying all rules, any remaining untagged cost goes to an UNALLOCATED TenantAttribution row. The AttributionPage renders this as its own row (CONTEXT.md decision). Never write a TenantProfile row for 'UNALLOCATED'.

**Warning signs:** Sum of tenant_attribution.total_cost does not match sum of billing_records.pre_tax_cost for that month.

### Pitfall 2: Rule Priority Ordering — Gaps and Duplicates

**What goes wrong:** If admin can delete or reorder rules, the `priority` integer column can end up with gaps (1, 3, 5) or duplicates. First-rule-wins logic can produce unpredictable results.

**Why it happens:** Naive delete/insert without renumbering.

**How to avoid:** The `POST /settings/rules/reorder` endpoint accepts an ordered list of rule IDs and renumbers priorities as 1, 2, 3... sequentially. Always renumber via this endpoint rather than allowing direct priority edits. Use `UniqueConstraint("priority")` at the DB layer to enforce uniqueness.

**Warning signs:** Two rules with the same priority integer, or rules that never match expected resources.

### Pitfall 3: Attribution Run Before Ingestion Completes

**What goes wrong:** If the attribution daily job runs at 03:00 UTC but ingestion hasn't landed all records yet (4-hour cycle, last run could be at 02:00), the daily snapshot captures incomplete data.

**Why it happens:** Scheduler jobs run independently with no dependency ordering.

**How to avoid:** Schedule attribution at 04:00 UTC (one hour after 03:00 ingestion window closes) or trigger attribution at the end of a successful ingestion run (post-ingestion hook, same pattern as anomaly detection hook in ingestion.py). The post-ingestion hook is simpler and guarantees fresh data.

**Warning signs:** Attribution totals for the current day are consistently lower than cost summary totals.

### Pitfall 4: manual_pct Percentages Not Summing to 100

**What goes wrong:** Admin enters 60% + 30% = 90%, leaving 10% unaccounted. The math silently produces a cost that doesn't balance.

**Why it happens:** No validation at save time.

**How to avoid:** Pydantic `@model_validator` on `AllocationRuleCreate` schema validates `sum(manual_pct.values()) == 100` when method is `manual_pct`. Return HTTP 422 with descriptive error if invalid.

**Warning signs:** UNALLOCATED bucket is larger than expected; manual_pct totals don't match rule target cost.

### Pitfall 5: Forgetting to Import attribution.py Models in Alembic env.py

**What goes wrong:** Alembic autogenerate doesn't detect new models because they aren't imported at migration time.

**Why it happens:** `migrations/env.py` only imports models that are explicitly imported. New model file is invisible to Alembic.

**How to avoid:** Add `import app.models.attribution` (or `from app.models.attribution import TenantProfile, AllocationRule, TenantAttribution`) to `migrations/env.py`. This is an explicit lesson from Phase 5 (see STATE.md: "migrations/env.py must import all model modules").

**Warning signs:** Running `alembic revision --autogenerate` produces an empty migration.

### Pitfall 6: Alembic JSON Column server_default

**What goes wrong:** Alembic autogenerate omits `server_default` for new columns on existing tables, causing NOT NULL violations on existing rows.

**Why it happens:** Alembic autogenerate does not add `server_default` for non-String columns.

**How to avoid:** For `manual_pct JSON NULLABLE=True`, this is not an issue (nullable). For any NOT NULL columns added later, add `server_default` manually. Follow Phase 3 precedent.

### Pitfall 7: by_usage Division-by-Zero When No Tagged Records Exist

**What goes wrong:** `by_usage` method divides untagged cost proportionally by tenant tagged cost. If no resources are tagged yet (first month, all costs untagged), division by zero.

**Why it happens:** Edge case in first-time setup or when all resources are in shared resource groups.

**How to avoid:** In `apply_rule()`, check `if total_tagged == 0: fallback to by_count`. This is already documented in the code example in Pattern 2 above.

---

## Code Examples

Verified patterns from established codebase:

### PostgreSQL Upsert (already used in ingestion.py)
```python
# Source: app/services/ingestion.py — exact same pattern for TenantAttribution upsert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.attribution import TenantAttribution

attribution_rows = [
    {"tenant_id": t_id, "year": year, "month": month,
     "total_cost": cost, "pct_of_total": pct, ...}
    for t_id, cost, pct in computed_attributions
]
stmt = pg_insert(TenantAttribution).values(attribution_rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["tenant_id", "year", "month"],
    set_={
        "total_cost": stmt.excluded.total_cost,
        "pct_of_total": stmt.excluded.pct_of_total,
        "computed_at": stmt.excluded.computed_at,
        "updated_at": stmt.excluded.updated_at,
    }
)
await session.execute(stmt)
await session.commit()
```

### CSV Export (already used in cost.py and anomaly.py)
```python
# Source: app/api/v1/cost.py — identical pattern for attribution export
import csv, io
from fastapi.responses import StreamingResponse

@router.get("/export")
async def export_attribution(year: int, month: int, ...):
    rows = await get_attributions(db, year=year, month=month)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["tenant_id", "display_name", "month", "total_cost_usd",
                     "pct_of_total", "mom_delta_usd", "top_service_category"])
    for row in rows:
        writer.writerow([
            row.tenant_id,
            row.display_name or row.tenant_id,
            f"{year}-{month:02d}",
            float(row.total_cost),
            float(row.pct_of_total),
            float(row.mom_delta_usd) if row.mom_delta_usd is not None else "",
            row.top_service_category or "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=attribution-{year}-{month:02d}.csv"},
    )
```

### Frontend CSV Blob Download (already used in Phase 3)
```typescript
// Source: established pattern from cost monitoring (Phase 3) and anomaly (Phase 4)
export async function exportAttribution(year: number, month: number): Promise<void> {
  const response = await api.get('/attribution/export', {
    params: { year, month },
    responseType: 'blob',
  });
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `attribution-${year}-${String(month).padStart(2, '0')}.csv`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}
```

### TanStack Query with Month/Year Params
```typescript
// Source: established pattern from cost.ts (useSpendBreakdown with multiple params)
export function useAttribution(year: number, month: number) {
  return useQuery<TenantAttribution[]>({
    queryKey: ['attribution', year, month],
    queryFn: async () => {
      const { data } = await api.get<TenantAttribution[]>('/attribution/', {
        params: { year, month },
      });
      return data;
    },
    staleTime: 5 * 60 * 1000,
  });
}
```

### Pydantic manual_pct Validator
```python
# Source: Pydantic v2 docs — model_validator for cross-field validation
from pydantic import BaseModel, model_validator

class AllocationRuleCreate(BaseModel):
    target_type: str    # 'resource_group' | 'service_category'
    target_value: str
    method: str         # 'by_count' | 'by_usage' | 'manual_pct'
    manual_pct: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_manual_pct(self):
        if self.method == "manual_pct":
            if not self.manual_pct:
                raise ValueError("manual_pct is required when method='manual_pct'")
            total = sum(self.manual_pct.values())
            if abs(total - 100.0) > 0.01:  # allow 0.01 floating point tolerance
                raise ValueError(f"manual_pct values must sum to 100 (got {total:.2f})")
        return self
```

### Post-Ingestion Attribution Hook (recommended approach for ATTR-01)
```python
# Source: established pattern from app/services/ingestion.py (anomaly detection hook)
# In ingestion.py _do_ingestion(), after successful commit:
from app.services.attribution import run_attribution

# At the end of a successful ingestion run (after anomaly detection):
try:
    await run_attribution()
    logger.info("Attribution run completed after ingestion")
except Exception as exc:
    logger.error("Attribution run failed after ingestion: %s", exc)
    # Non-fatal — attribution failure should not fail the ingestion run record
```

---

## State of the Art

| Old Approach | Current Approach | Impact for Phase 6 |
|--------------|------------------|--------------------|
| Dynamic cost allocation computed at query time | Pre-computed monthly snapshots (OLAP-style) | Attribution view loads instantly; no complex query at request time |
| External cost allocation tools (Apptio, CloudHealth) | Native tag-based allocation in app service layer | No new infrastructure; all data already in billing_records |
| Modal-based form entry | Inline row editing in table | CONTEXT.md locked decision; matches shadcn table patterns |

**No deprecated approaches apply to this phase.** All patterns (APScheduler, pg_insert upsert, TanStack Query, StreamingResponse CSV) are current.

---

## Open Questions

1. **Per-tenant breakdown endpoint: computed or raw?**
   - What we know: The expandable row shows "cost breakdown by service category for that tenant"
   - What's unclear: Should this query `billing_records` grouped by service on the fly (fresh but slower), or should service-category breakdown be pre-computed alongside the monthly total?
   - Recommendation: Query `billing_records` on the fly for the breakdown detail view — only triggered per click, not on initial page load. Simple `SELECT service_name, SUM(pre_tax_cost) FROM billing_records WHERE tag=? AND month=?` is fast for 30 tenants and avoids schema complexity.

2. **Priority reordering UX — left to Claude's discretion**
   - What we know: CONTEXT.md marks this as Claude's discretion ("drag-and-drop vs. numbered input")
   - Recommendation: Use a numbered input (simple `<Input type="number">` in the rules table) rather than drag-and-drop. Drag-and-drop requires an additional library (dnd-kit or similar) and is unnecessary for a short rules list (likely <10 rules). Numbered input works with existing Input component.

3. **Attribution run timing: post-ingestion hook vs. standalone cron**
   - What we know: Ingestion runs every 4 hours; anomaly detection already hooks into post-ingestion
   - Recommendation: Attach attribution as a post-ingestion hook (same pattern as anomaly detection), not a separate cron. This ensures attribution always reflects the latest ingested data and avoids scheduling coordination complexity.

---

## Sources

### Primary (HIGH confidence)
- Codebase analysis — `app/models/billing.py`: BillingRecord.tag stores raw tenant_id values (empty string for untagged); confirmed Phase 3 forward-seeding decision
- Codebase analysis — `app/services/ingestion.py`: pg_insert upsert pattern verified; post-ingestion hook pattern verified (anomaly detection)
- Codebase analysis — `app/api/v1/cost.py`: StreamingResponse CSV pattern verified; `io.StringIO` + `csv.writer` confirmed
- Codebase analysis — `app/main.py`: APScheduler CronTrigger registration pattern confirmed; lifespan structure confirmed
- Codebase analysis — `frontend/src/services/anomaly.ts`: TanStack Query hooks, useMutation, queryClient.invalidateQueries patterns verified
- Codebase analysis — `frontend/src/components/ui/table.tsx`: Table component already installed
- Codebase analysis — `frontend/src/App.tsx`: `/attribution` and `/settings` routes already commented as Phase 6 targets
- Codebase analysis — `frontend/src/components/AppSidebar.tsx`: Attribution and Settings nav items already present in navItems array
- SQLAlchemy 2.0 docs (training knowledge, HIGH confidence for stable ORM patterns) — `JSON` column type, `on_conflict_do_update`
- Pydantic v2 docs (training knowledge, HIGH confidence) — `@model_validator(mode="after")` for cross-field validation

### Secondary (MEDIUM confidence)
- STATE.md decision log — "migrations/env.py must import all model modules" (Phase 5 lesson)
- STATE.md decision log — "server_default='' added manually to autogenerated Alembic migration" (Phase 3 lesson)
- STATE.md decision log — "tag column stores raw tenant_id tag value (empty string for untagged) — satisfies COST-04 and pre-seeds Phase 6 attribution" (Phase 3 confirmation)

### Tertiary (LOW confidence)
- None. All findings are verified from codebase or established project patterns.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all libraries already installed and verified in codebase
- Data model: HIGH — based on direct codebase analysis and established SQLAlchemy patterns
- Architecture patterns: HIGH — all patterns are established in the existing codebase (ingestion, cost, anomaly)
- Pitfalls: HIGH — most pitfalls derive directly from project STATE.md lessons and code analysis
- Frontend UI patterns: HIGH — shadcn Table, TanStack Query, and blob download all verified in existing code

**Research date:** 2026-02-21
**Valid until:** 2026-04-01 (stable stack; no fast-moving external dependencies)
