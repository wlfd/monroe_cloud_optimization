---
phase: 04-anomaly-detection
verified: 2026-02-21T12:00:00Z
status: passed
score: 19/19 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Navigate to /anomalies and interact with the full lifecycle (Investigate, Dismiss, Mark as Expected, Revert to New, Unmark Expected)"
    expected: "Status badges update instantly, counters in KPI cards refresh, no page reload required"
    why_human: "Real-time mutation behavior and optimistic UI cannot be verified with static grep; already confirmed by human UAT during Plan 05"
  - test: "Click Export Report on the Anomalies page"
    expected: "anomaly-report.csv downloads with correct header row and data rows"
    why_human: "File download and CSV content correctness requires a running browser and real data"
---

# Phase 4: Anomaly Detection Verification Report

**Phase Goal:** The system automatically surfaces unusual spending spikes with severity ratings and dollar impact so users can investigate quickly
**Verified:** 2026-02-21T12:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 30-day rolling baseline detection runs after each ingestion cycle | VERIFIED | `run_anomaly_detection(session)` called at line 335 of `ingestion.py` after `upsert_billing_records` commits (line 334), before `clear_active_alerts` (line 336) |
| 2 | Anomalies are assigned severity (Critical/High/Medium) based on monthly dollar impact | VERIFIED | `anomaly.py` lines 141-147: `>= 1000 => critical`, `>= 500 => high`, else `medium`; 20% deviation + $100 noise floor applied first |
| 3 | Estimated monthly dollar impact calculated and stored per anomaly | VERIFIED | `estimated_monthly_impact = (current - baseline_avg) * 30` (line 135 of `anomaly.py`); stored in `Anomaly.estimated_monthly_impact` column |
| 4 | Re-detection on same (service, resource_group, date) preserves user-set status | VERIFIED | `upsert_anomaly` uses `pg_insert ON CONFLICT DO UPDATE`; `set_` dict explicitly excludes `status` and `expected` (lines 221-229) |
| 5 | GET /api/v1/anomalies/ returns anomaly list with severity and impact | VERIFIED | `list_anomalies` endpoint at line 31 of `anomaly.py` router; calls `get_anomalies()` and maps with `AnomalyResponse.model_validate(row)` |
| 6 | GET /api/v1/anomalies/summary returns 7-field KPI response | VERIFIED | `anomaly_summary` endpoint at line 51; `get_anomaly_summary()` returns dict with all 7 keys: `active_count`, `critical_count`, `high_count`, `medium_count`, `total_potential_impact`, `resolved_this_month`, `detection_accuracy` |
| 7 | PATCH /{id}/status updates status to investigating/resolved/dismissed/new | VERIFIED | `update_status` endpoint at line 123; `_VALID_STATUSES = {"new", "investigating", "resolved", "dismissed"}`; 400 on invalid, 404 on not found |
| 8 | PATCH /{id}/expected toggles expected flag and status | VERIFIED | `mark_expected` endpoint at line 142; handles `expected=true` (marks + dismisses) and `expected=false` (clears + resets to new) via `unmark_anomaly_expected()` |
| 9 | GET /api/v1/anomalies/export returns CSV download | VERIFIED | `export_anomalies` endpoint at line 61; `StreamingResponse` with `Content-Disposition: attachment; filename=anomaly-report.csv`; 8-column CSV written with `csv.writer` |
| 10 | User can view anomaly list with filter dropdowns (severity, service, resource group) | VERIFIED | `AnomaliesPage.tsx` lines 354-393: three Select components for Service, Resource Group, Severity; filters passed to `useAnomalies()` hook |
| 11 | Anomaly cards show colored severity dots, badges, description, impact in red | VERIFIED | `AnomalyCard` sub-component (lines 41-194): `severityDotColor` map → `w-3 h-3 rounded-full`, severity `Badge`, status `Badge`, `+{impactFormatted}` in `text-red-600` |
| 12 | Lifecycle action buttons (Investigate, Dismiss, Mark as Expected, Revert, Unmark) work with context-sensitive rendering | VERIFIED | `AnomalyCard` lines 99-182: conditional rendering by `isNew`/`isInvestigating`/`isDismissed`/`isExpected` flags; all mutations wired to `updateStatus.mutate()`, `markExpected.mutate()`, `unmarkExpected.mutate()` |
| 13 | Export Report button triggers CSV download | VERIFIED | `handleExport` at line 219; calls `exportAnomalies()` from anomaly service with active filters |
| 14 | 4 KPI summary cards at top of Anomalies page | VERIFIED | `AnomaliesPage.tsx` lines 253-350: Active Anomalies, Potential Impact, Resolved This Month, Detection Accuracy — all reading from `summary` (useAnomalySummary) |
| 15 | Severity summary line shows Critical/High/Medium counts | VERIFIED | `severityBreakdownParts` computed at lines 231-235; rendered in both KPI card (line 275) and section header (line 399) |
| 16 | Detection Configuration panel at page bottom | VERIFIED | Lines 430-451: Card with Baseline Period (30 days), Minimum Deviation (20%), Severity Thresholds |
| 17 | Dashboard shows Active Anomalies KPI card linking to /anomalies | VERIFIED | `DashboardPage.tsx` lines 187-234: 4th card with `useAnomalySummary()`, count in red when > 0, worst-severity label, `Link to="/anomalies"` at line 226 |
| 18 | Dashboard KPI grid updated to 4 columns | VERIFIED | `DashboardPage.tsx` line 114: `grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4` |
| 19 | anomalies table has unique constraint and 3 indexes | VERIFIED | Migration `37031473bbfa` lines 40-44: `uq_anomaly_key` on (service_name, resource_group, detected_date), `idx_anomaly_detected_date`, `idx_anomaly_severity`, `idx_anomaly_status` |

**Score:** 19/19 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/models/billing.py` | Anomaly ORM model with 14 columns, unique constraint, 3 indexes | VERIFIED | Lines 85-108; all columns present, `__table_args__` includes `UniqueConstraint("service_name", "resource_group", "detected_date", name="uq_anomaly_key")` and 3 `Index()` entries |
| `backend/migrations/versions/37031473bbfa_add_anomalies_table.py` | Alembic migration creating anomalies table | VERIFIED | 56 lines; `op.create_table('anomalies', ...)` with all 14 columns, `server_default='new'` on status, `server_default='false'` on expected; 3 indexes created |
| `backend/app/services/anomaly.py` | 9 functions (including unmark_anomaly_expected added in Plan 05) | VERIFIED | 493 lines; all 9 functions: `run_anomaly_detection`, `upsert_anomaly`, `auto_resolve_anomalies`, `get_anomalies`, `get_anomaly_summary`, `update_anomaly_status`, `mark_anomaly_expected`, `unmark_anomaly_expected`, `get_anomalies_for_export` |
| `backend/app/schemas/anomaly.py` | 4 Pydantic models | VERIFIED | 43 lines; `AnomalyResponse` (with `from_attributes=True`), `AnomalySummaryResponse`, `AnomalyStatusUpdate`, `AnomalyMarkExpectedRequest` |
| `backend/app/api/v1/anomaly.py` | FastAPI router with 6 endpoints under /anomalies prefix | VERIFIED | 161 lines; GET `/`, GET `/summary`, GET `/export`, GET `/filter-options`, PATCH `/{id}/status`, PATCH `/{id}/expected` — all with `get_current_user` dependency |
| `backend/app/api/v1/router.py` | Anomaly router registered with prefix /anomalies | VERIFIED | Line 9: `api_router.include_router(anomaly_router_module.router, prefix="/anomalies", tags=["anomalies"])` |
| `backend/app/services/ingestion.py` | `run_anomaly_detection` imported and called post-upsert | VERIFIED | Line 21: import; line 335: called after `upsert_billing_records` (line 334) commits; before `clear_active_alerts` (line 336) |
| `frontend/src/services/anomaly.ts` | TanStack Query hooks and TypeScript interfaces | VERIFIED | 130 lines; exports: `Anomaly`, `AnomalySummary`, `AnomalyFilters`, `useAnomalies`, `useAnomalySummary`, `useUpdateAnomalyStatus`, `useMarkAnomalyExpected`, `useUnmarkAnomalyExpected`, `exportAnomalies` |
| `frontend/src/App.tsx` | Route `/anomalies` wired to AnomaliesPage | VERIFIED | Line 8: import; line 25: `{ path: '/anomalies', element: <AnomaliesPage /> }` |
| `frontend/src/components/ui/badge.tsx` | shadcn Badge component | VERIFIED | 49 lines; exports `Badge` and `badgeVariants`; uses `cva` from class-variance-authority |
| `frontend/src/pages/AnomaliesPage.tsx` | Full anomalies page (min 200 lines) | VERIFIED | 454 lines; contains KPI cards, filter dropdowns, AnomalyCard sub-component with mutations, export handler, detection config panel |
| `frontend/src/pages/DashboardPage.tsx` | Updated KPI grid with anomaly summary card | VERIFIED | `useAnomalySummary` imported (line 40), called (line 81); `lg:grid-cols-4` at line 114; Active Anomalies card at lines 187-234 with `Link to="/anomalies"` |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `ingestion.py` `_do_ingestion()` | `anomaly.py` `run_anomaly_detection()` | Direct call after `upsert_billing_records` commits | WIRED | Line 335: `await run_anomaly_detection(session)` |
| `anomaly.py` router endpoints | `services/anomaly.py` service functions | Direct `await` calls in each handler | WIRED | `get_anomalies`, `get_anomaly_summary`, `update_anomaly_status`, `mark_anomaly_expected`, `unmark_anomaly_expected`, `get_anomalies_for_export` all called in endpoints |
| `router.py` | `api/v1/anomaly.py` router | `api_router.include_router(anomaly_router_module.router, prefix="/anomalies")` | WIRED | Line 9 of router.py |
| `AnomaliesPage.tsx` | `services/anomaly.ts` | Named imports: `useAnomalies`, `useAnomalySummary`, `useUpdateAnomalyStatus`, `useMarkAnomalyExpected`, `useUnmarkAnomalyExpected`, `exportAnomalies` | WIRED | Lines 9-16; all hooks called in component body and AnomalyCard sub-component |
| `DashboardPage.tsx` | `services/anomaly.ts` | `useAnomalySummary` import and call | WIRED | Line 40: import; line 81: `const anomalySummary = useAnomalySummary()` |
| `DashboardPage.tsx` | `/anomalies` route | `Link to="/anomalies"` inside Active Anomalies card | WIRED | Line 226: `to="/anomalies"` |
| `App.tsx` | `AnomaliesPage.tsx` | React Router `<Route path='/anomalies' element={<AnomaliesPage />} />` | WIRED | Lines 8, 25 |
| `services/anomaly.ts` `useAnomalies` | `GET /api/v1/anomalies/` | `api.get('/anomalies/', { params })` in queryFn | WIRED | Line 50: correct path, params forwarded |
| `services/anomaly.ts` `useUpdateAnomalyStatus` | `PATCH /api/v1/anomalies/{id}/status` | `api.patch('/anomalies/${id}/status', { status })` | WIRED | Line 74 |

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ANOMALY-01 | 04-01, 04-02 | System detects spending anomalies via 30-day rolling baseline per (service, resource group) pair | SATISFIED | `run_anomaly_detection()` computes 2-step SQL subquery baseline (daily_sub → baseline_stmt) using `func.avg(func.sum(...))` per `(service_name, resource_group)` pair; applied via Alembic migration `37031473bbfa` |
| ANOMALY-02 | 04-01, 04-02 | System assigns severity (Critical/High/Medium) based on estimated monthly dollar impact | SATISFIED | Severity classification at `anomaly.py` lines 141-147: `>= $1000 => critical`, `>= $500 => high`, `< $500 (and >= $100) => medium`; severity stored in DB and exposed via API |
| ANOMALY-03 | 04-01, 04-02 | System calculates estimated monthly dollar impact for each detected anomaly | SATISFIED | `estimated_monthly_impact = (current - baseline_avg) * 30` (lines 135-138); stored as `Numeric(18,2)`; returned in `AnomalyResponse` and displayed on each card in red (`+{impactFormatted}`) |
| ANOMALY-04 | 04-03, 04-04, 04-05 | User can view a list of anomalies with severity, affected service, and dollar impact | SATISFIED | `AnomaliesPage.tsx` (454 lines): card-list view with severity dots, severity/status badges, service name, impact in red; filter dropdowns for service/resource_group/severity; lifecycle actions; Export Report; Dashboard summary card; all backed by authenticated API endpoints |

All 4 required requirement IDs from PLAN frontmatter are fully accounted for. No orphaned requirements found — REQUIREMENTS.md traceability table marks all 4 as Complete under Phase 4.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `AnomaliesPage.tsx` | 176-181 | View Resources button is `disabled` with no action | Info | Intentional per plan spec ("render as non-functional placeholder"); does not block any anomaly goal behavior |

No blocker or warning-level anti-patterns found. The disabled "View Resources" button was explicitly specified in 04-04-PLAN.md as a non-functional placeholder pending a future resource detail page.

---

### Human Verification Required

Human UAT was completed and signed off during Plan 05 (2026-02-21). The following items remain as record of what was verified by human:

#### 1. Full anomaly lifecycle UI

**Test:** Navigate to `/anomalies` with test data; click Investigate, then Revert to New; click Dismiss on another; click Mark as Expected; click Unmark Expected
**Expected:** Status badges update without page reload; KPI counters refresh; active count decrements when items are dismissed/resolved
**Why human:** Real-time optimistic UI behavior, badge color transitions, and counter synchronization cannot be verified with static analysis. Previously confirmed by human reviewer (Plan 05 sign-off).

#### 2. CSV export correctness

**Test:** Click Export Report on `/anomalies`
**Expected:** `anomaly-report.csv` downloads; headers are `detected_date, service_name, resource_group, severity, status, pct_deviation, estimated_monthly_impact, description`; data rows contain correct values
**Why human:** File download mechanism and content correctness require a live browser and real anomaly data. CSV header/column structure is statically verified in `anomaly.py` router lines 72-81.

---

### Gaps Summary

No gaps. All automated checks passed. Phase 4 goal fully achieved.

The one notable post-plan addition was the undo/revert capability (Plan 05 remediation): context-sensitive action buttons and `unmark_anomaly_expected()` backend function were added after human UAT identified the UX gap. These additions are fully wired and verified above.

---

## Commit Traceability

All 7 phase commits confirmed in git log:

| Commit | Description | Plan |
|--------|-------------|------|
| `a2da223` | feat(04-01): add Anomaly SQLAlchemy model and anomalies table migration | 04-01 |
| `3587ae2` | feat(04-02): implement anomaly detection service | 04-02 Task 1 |
| `e2f1aa4` | feat(04-02): wire post-ingestion hook, schemas, API router | 04-02 Task 2 |
| `da1de86` | feat(04-03): install Badge, create anomaly service, wire /anomalies route | 04-03 |
| `b0657ac` | feat(04-04): build full AnomaliesPage | 04-04 Task 1 |
| `ff7edb5` | feat(04-04): add Active Anomalies KPI card to Dashboard | 04-04 Task 2 |
| `fe6b9a3` | feat(04-05): add undo/revert buttons for all anomaly status-changing actions | 04-05 (UAT remediation) |

---

_Verified: 2026-02-21T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
