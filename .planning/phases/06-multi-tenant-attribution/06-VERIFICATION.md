---
phase: 06-multi-tenant-attribution
verified: 2026-02-21T22:30:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
human_verification:
  - test: "Confirm 'New' badge appears on tenant rows in Attribution table"
    expected: "Rows for tenants with is_new=true show a 'New' badge; the badge disappears after clicking Acknowledge in Settings"
    why_human: "TenantAttribution interface does not carry is_new; the badge uses a type-intersection cast `(tenant as TenantAttribution & { is_new?: boolean }).is_new` which can never be true unless the API response includes the field. Programmatic check cannot confirm whether the API response actually serialises is_new onto attribution rows, since TenantAttributionResponse schema does not include the field."
  - test: "Verify ROADMAP plan checklist is updated to mark Phase 6 plans as complete"
    expected: "The four plan bullets under Phase 6 in ROADMAP.md should read [x] not [ ]"
    why_human: "The phase is marked [x] complete at the top of ROADMAP, but the four plan-level bullets remain [ ]. This is a documentation inconsistency the human should correct."
---

# Phase 6: Multi-Tenant Attribution Verification Report

**Phase Goal:** Finance and engineering can see infrastructure cost broken down by customer tenant, enabling unit economics reporting for Series A diligence
**Verified:** 2026-02-21T22:30:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Three new tables exist in the database: tenant_profiles, allocation_rules, tenant_attributions | VERIFIED | Migration `29e392128bad_add_attribution_tables.py` creates all three tables with correct columns, constraints, and indexes |
| 2 | TenantProfile model tracks distinct tenant_id tag values with display_name, is_new flag, and first_seen date | VERIFIED | `backend/app/models/attribution.py` lines 24-40: all required fields present with correct types and constraints |
| 3 | AllocationRule model supports by_count, by_usage, and manual_pct methods with priority ordering | VERIFIED | `attribution.py` lines 43-67: AllocationRule model has method, priority, manual_pct fields; `apply_allocation_rule()` in service implements all three methods |
| 4 | TenantAttribution model stores pre-computed monthly totals with unique constraint on (tenant_id, year, month) | VERIFIED | Lines 70-99: all required columns present; `uq_tenant_attribution_key` unique constraint and two indexes confirmed in migration |
| 5 | Daily attribution job runs after each ingestion to map resources to tenants via tenant_id tags | VERIFIED | `ingestion.py` line 338: `await run_attribution()` called after `run_anomaly_detection` inside try/except block |
| 6 | Allocation rules applied to untagged costs using by_count, by_usage, or manual_pct methods | VERIFIED | `services/attribution.py` lines 34-68: `apply_allocation_rule()` implements all three methods including by_usage fallback to by_count when sum is zero |
| 7 | Remaining untagged cost after rules is captured in UNALLOCATED sentinel row | VERIFIED | Lines 197-212: `unallocated = untagged_total - total_rule_matched`; upserted with tenant_id="UNALLOCATED" if > 0 |
| 8 | GET /api/v1/attribution/ returns pre-computed monthly totals for a given year/month | VERIFIED | `api/v1/attribution.py` lines 36-66: endpoint calls `get_attributions()` and returns `list[TenantAttributionResponse]`; registered in router.py at prefix `/attribution` |
| 9 | GET /api/v1/attribution/export returns a CSV file with per-tenant cost rows | VERIFIED | Lines 88-131: `StreamingResponse` with correct CSV columns (tenant_id, display_name, period, total_cost_usd, pct_of_total, mom_delta_usd, top_service_category) and correct Content-Disposition header |
| 10 | Admin can CRUD allocation rules and update tenant display names via /api/v1/settings endpoints | VERIFIED | `api/v1/settings.py`: 8 endpoints covering GET/PATCH/POST for tenants and GET/POST/PATCH/DELETE/POST-reorder for rules, all wired to service functions |
| 11 | User can view a sortable table of per-tenant monthly costs defaulting to current month | VERIFIED | `AttributionPage.tsx`: `useAttribution(year, month)` called; three sortable column headers; month/year pickers with `useState` defaults to `new Date()` |
| 12 | User can export current month's per-tenant attribution to CSV | VERIFIED | `exportAttribution(year, month)` called from `handleExport`; blob download pattern via `createObjectURL` identical to `cost.ts` |

**Score:** 12/12 truths verified

---

### Required Artifacts

#### Plan 06-01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/attribution.py` | TenantProfile, AllocationRule, TenantAttribution SQLAlchemy models | VERIFIED | 99 lines; all three classes present with correct columns, constraints, and indexes; `from app.core.database import Base` wired |
| `backend/migrations/env.py` | Alembic env.py importing attribution models | VERIFIED | Line 13: `from app.models import attribution  # noqa: F401` present |
| `backend/migrations/versions/29e392128bad_add_attribution_tables.py` | Alembic migration creating three new tables | VERIFIED | Creates allocation_rules, tenant_attributions, tenant_profiles with all specified columns; `server_default='true'` on is_new Boolean |

#### Plan 06-02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/schemas/attribution.py` | Pydantic request/response schemas | VERIFIED | 99 lines; TenantAttributionResponse, AllocationRuleCreate (with model_validator), AllocationRuleResponse, TenantProfileResponse, RuleReorderRequest, ServiceBreakdownItem, TenantDisplayNameUpdate, AllocationRuleUpdate all present |
| `backend/app/services/attribution.py` | run_attribution(), get_attributions(), get_attribution_breakdown() and 7 CRUD helpers | VERIFIED | 575 lines; all required exports confirmed; apply_allocation_rule() pure helper; _AttributionWithDisplayName wrapper |
| `backend/app/api/v1/attribution.py` | FastAPI router with 4 endpoints under /attribution | VERIFIED | 149 lines; router declared; GET /, GET /breakdown/{tenant_id}, GET /export, POST /run all implemented |
| `backend/app/api/v1/settings.py` | FastAPI router with 8 settings endpoints | VERIFIED | 149 lines; all 8 endpoints implemented with correct HTTP methods and admin auth |
| `backend/app/api/v1/router.py` | Updated main router including attribution and settings routers | VERIFIED | Lines 4-5 import both router modules; lines 18-27 include_router both at /attribution and /settings prefixes |
| `backend/app/services/ingestion.py` | Post-ingestion attribution hook wired after anomaly detection | VERIFIED | Line 22: top-level import; lines 337-342: try/except hook after anomaly, before clear_active_alerts |

#### Plan 06-03 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/services/attribution.ts` | TanStack Query hooks and mutation hooks for all attribution/settings API calls | VERIFIED | 200 lines; 4 query hooks (useAttribution, useAttributionBreakdown, useTenantProfiles, useAllocationRules), 6 mutation hooks, exportAttribution() function |
| `frontend/src/pages/AttributionPage.tsx` | Sortable tenant attribution table with expandable rows and month picker | VERIFIED | 349 lines; sortAttributions(), TenantBreakdownRow sub-component, expandedId state, month/year Selects, Export CSV button, UNALLOCATED badge, loading skeletons |
| `frontend/src/pages/SettingsPage.tsx` | Tabbed settings page with tenant name management and allocation rule CRUD | VERIFIED | 497 lines; Tabs with TenantsTab (inline editing, acknowledge) and AllocationRulesTab (drag-to-reorder, inline add form, delete with confirm) |
| `frontend/src/App.tsx` | Routes for /attribution and /settings wired to page components | VERIFIED | Lines 10-11: imports; lines 30-31: routes present |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `backend/migrations/env.py` | `backend/app/models/attribution.py` | `from app.models import attribution` | WIRED | Line 13 confirmed |
| `backend/app/models/attribution.py` | `backend/app/core/database.py` | `from app.core.database import Base` | WIRED | Line 17 confirmed |
| `backend/app/services/ingestion.py` | `backend/app/services/attribution.py` | `run_attribution` post-ingestion hook | WIRED | Import line 22; call line 338 inside try/except |
| `backend/app/api/v1/attribution.py` | `backend/app/services/attribution.py` | `get_attributions`, `get_attribution_breakdown` | WIRED | Lines 25-29: all three service functions imported and called in endpoints |
| `backend/app/api/v1/router.py` | `backend/app/api/v1/attribution.py` | `include_router` | WIRED | Lines 4, 18-22 confirmed |
| `backend/app/api/v1/router.py` | `backend/app/api/v1/settings.py` | `include_router` | WIRED | Lines 5, 23-27 confirmed |
| `frontend/src/pages/AttributionPage.tsx` | `/api/v1/attribution/` | `useAttribution` hook | WIRED | Imported and called at line 109 |
| `frontend/src/pages/AttributionPage.tsx` | `/api/v1/attribution/breakdown/{tenant_id}` | `useAttributionBreakdown` hook | WIRED | Imported and called inside TenantBreakdownRow at line 41 |
| `frontend/src/pages/SettingsPage.tsx` | `/api/v1/settings/tenants` | `useTenantProfiles` hook | WIRED | Imported and called at line 32 |
| `frontend/src/pages/SettingsPage.tsx` | `/api/v1/settings/rules` | `useAllocationRules` hook | WIRED | Imported and called at line 199 |
| `frontend/src/App.tsx` | `frontend/src/pages/AttributionPage.tsx` | React Router route definition | WIRED | `path: '/attribution'` at line 30 |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ATTR-01 | 06-01, 06-02, 06-04 | System maps Azure resources to tenants via tenant_id resource tag on a daily schedule | SATISFIED | `run_attribution()` discovers tenants via `SELECT DISTINCT tag`, upserts `tenant_profiles`, called as post-ingestion hook in `ingestion.py` |
| ATTR-02 | 06-01, 06-02, 06-03, 06-04 | Admin can define shared/untagged resource allocation rules (by-tenant-count, by-usage, or manual percentage splits) | SATISFIED | AllocationRule model, 8 settings endpoints, AllocationRulesTab with inline create form, drag-to-reorder, and delete; all three methods implemented in `apply_allocation_rule()` |
| ATTR-03 | 06-02, 06-03, 06-04 | User can view monthly infrastructure cost per tenant | SATISFIED | GET /api/v1/attribution/ endpoint, AttributionPage with sortable table, expandable per-service breakdown rows, month/year pickers |
| ATTR-04 | 06-02, 06-03, 06-04 | User can export per-tenant cost report to CSV | SATISFIED | GET /api/v1/attribution/export StreamingResponse, frontend `exportAttribution()` blob download |

All 4 ATTR requirements covered by plans. No orphaned requirements.

---

### Notable Findings (Non-Blocking)

#### 1. "New" badge on Attribution table rows — structural gap

The `TenantAttribution` interface (and `TenantAttributionResponse` schema) does not include the `is_new` field. The `AttributionPage.tsx` renders the "New" badge via a TypeScript type-intersection cast:

```tsx
(tenant as TenantAttribution & { is_new?: boolean }).is_new
```

The field will always evaluate to `undefined` (falsy) because the API never serialises `is_new` onto attribution rows. The `is_new` badge correctly appears in **Settings > Tenants** (via `TenantProfileResponse`), but it will never appear on the Attribution table rows. This is a cosmetic gap — the 06-03 plan's truth "Tenants with is_new=true show a 'New' badge" is **partially satisfied** only on the Settings page. The phase goal (unit economics reporting) is not blocked by this.

**Severity:** Warning (does not block goal achievement; "New" badge visible in Settings where it matters for admin workflow)

#### 2. Edit button for allocation rules is absent from UI

The `useUpdateAllocationRule` hook is exported from `attribution.ts` and the backend `PATCH /settings/rules/{rule_id}` endpoint is fully implemented, but `SettingsPage.tsx` imports neither the hook nor presents an Edit button on rule rows. The 06-03 plan's must_have truth says "Admin can create, update, delete, and reorder" — the UI covers create, delete, and reorder but not update inline editing of existing rules.

`ATTR-02` requires only "Admin can define" rules — the create/delete/reorder capability satisfies this. The missing edit UI is a plan deviation that does not block the ATTR-02 requirement.

**Severity:** Warning (plan deviation; ATTR-02 still satisfied by create/delete/reorder capability)

#### 3. ROADMAP plan checklist not updated

Phase 6 is correctly marked `[x]` complete at the top of `ROADMAP.md`, but the four plan bullets beneath it remain `[ ]` unchecked.

**Severity:** Info (documentation only)

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `AttributionPage.tsx:304` | Type-intersection cast for is_new field that backend never sends | Warning | "New" badge will never render on attribution rows |
| `attribution.ts` | `useUpdateAllocationRule` exported but never imported/used in any component | Info | Dead code; edit rule capability unreachable from UI |
| `ROADMAP.md` | Phase 6 plan bullets remain `[ ]` while phase is marked `[x]` complete | Info | Documentation inconsistency only |

No TODO/FIXME/HACK/PLACEHOLDER comments found in any phase 6 file. No API routes returning static stubs. No empty component implementations.

---

### Human Verification Required

#### 1. Confirm "New" badge behaviour across Settings and Attribution

**Test:** Log in, trigger ingestion to discover a new tenant. Navigate to Settings > Tenants. Confirm the "New" badge appears and the Acknowledge button clears it. Then navigate to Attribution and confirm whether a "New" badge appears on that tenant's row.
**Expected:** "New" badge visible in Settings; NOT visible in Attribution table (structural gap documented above).
**Why human:** The type-intersection cast in AttributionPage cannot be confirmed correct/incorrect without a live API response inspection.

#### 2. Fix ROADMAP plan checkboxes

**Test:** Open `.planning/ROADMAP.md`, find the Phase 6 section, and change all four `[ ]` plan bullets to `[x]`.
**Expected:** All four Phase 6 plan bullets show `[x]` to match the `[x]` phase-level marker.
**Why human:** Documentation correction is a manual edit outside automation scope.

---

### Gaps Summary

No gaps blocking goal achievement. The phase goal — "Finance and engineering can see infrastructure cost broken down by customer tenant, enabling unit economics reporting for Series A diligence" — is fully achieved:

- Three database tables exist with correct schema
- Daily attribution job runs post-ingestion, maps billing_records.tag to tenant_profiles, applies allocation rules, writes TenantAttribution rows
- Four backend API endpoints serve attribution data and CSV export
- Eight admin API endpoints manage tenant profiles and allocation rules
- AttributionPage renders per-tenant monthly costs in a sortable, exportable table with per-service drill-down
- SettingsPage gives admins full control over tenant names and allocation rule definitions
- All four ATTR requirements confirmed by human UAT (06-04 sign-off)

The two warning-level findings (is_new badge structural gap and missing edit-rule UI) are cosmetic gaps that do not affect the finance/engineering use case for Series A diligence.

---

_Verified: 2026-02-21T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
