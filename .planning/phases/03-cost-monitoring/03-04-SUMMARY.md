---
phase: 03-cost-monitoring
plan: "04"
subsystem: ui
tags: [react, shadcn, tanstack-query, recharts, csv-export, typescript]

# Dependency graph
requires:
  - phase: 03-cost-monitoring
    plan: "02"
    provides: "useSpendBreakdown, useTopResources hooks wired to /api/v1/costs/breakdown and /api/v1/costs/top-resources"
  - phase: 03-cost-monitoring
    plan: "03"
    provides: "DashboardPage with KPI cards, trend AreaChart, days state, and useSpendTrend"
provides:
  - "Cost Breakdown card with shadcn Select dimension picker (service/resource_group/region/tag) and sortable table"
  - "Export CSV button with blob download pattern (responseType: blob + createObjectURL)"
  - "Top 10 Most Expensive Resources table with resource_name/service/resource_group/cost columns and empty state"
  - "Complete dashboard satisfying all 6 COST requirements (COST-01 through COST-06) end-to-end"
affects:
  - phase: 04-anomaly-detection
  - phase: 05-recommendations
  - phase: 06-attribution

# Tech tracking
tech-stack:
  added:
    - "shadcn/ui select component (radix-ui/react-select)"
    - "shadcn/ui table component (semantic HTML table primitives)"
  patterns:
    - "Blob download pattern: api.get with responseType: blob + createObjectURL + programmatic link click + revokeObjectURL"
    - "Dimension selector pattern: string state drives both queryKey and export params — single source of truth"
    - "Empty state pattern: ternary on data.length > 0 with loading/no-data messages"

key-files:
  created:
    - "frontend/src/components/ui/select.tsx"
    - "frontend/src/components/ui/table.tsx"
  modified:
    - "frontend/src/pages/DashboardPage.tsx"
    - "frontend/src/pages/IngestionPage.tsx"

key-decisions:
  - "Export button placed inline in Cost Breakdown card header (right of Select) — keeps action contextual to the data being viewed"
  - "Export uses api singleton directly (not a hook) — one-time action, not server state; hooks are for queries not mutations"
  - "dimension and days params both sent to /costs/export — CSV filename includes both for unambiguous identification"

patterns-established:
  - "Blob download: responseType: blob + createObjectURL + link.click() + revokeObjectURL — established for any future CSV/PDF exports"
  - "shadcn Table: semantic TableHeader/TableBody/TableRow/TableHead/TableCell pattern for all data tables going forward"
  - "shadcn Select: SelectTrigger + SelectContent + SelectItem pattern for all dimension/filter pickers"

requirements-completed: [COST-04, COST-05, COST-06]

# Metrics
duration: 2min
completed: 2026-02-21
---

# Phase 3 Plan 04: Cost Breakdown + Top Resources + CSV Export Summary

**Complete dashboard with shadcn Select dimension picker, sortable cost breakdown table, top-10 resources table, and CSV export via blob download pattern — satisfying COST-04, COST-05, COST-06**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-21T07:08:57Z
- **Completed:** 2026-02-21T07:11:03Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Installed shadcn `select` and `table` UI primitives via shadcn CLI
- Added Cost Breakdown card to DashboardPage with 4-option dimension Select (Service / Resource Group / Region / Tag), data table, and Export CSV button
- Added Top 10 Most Expensive Resources card with 4-column table (Resource, Service, Resource Group, Total Cost) and informative empty state message
- Export CSV button uses blob download pattern: `responseType: "blob"` + `createObjectURL` + programmatic link click + `revokeObjectURL`
- TypeScript compiles clean (`tsc --noEmit` zero errors); Vite production build succeeds in 1.54s

## Task Commits

Each task was committed atomically:

1. **shadcn components install** - `6a33820` (feat)
2. **DashboardPage breakdown + top resources + export** - `f17a813` (feat)

**Plan metadata:** (docs commit — see final_commit below)

## Files Created/Modified

- `frontend/src/components/ui/select.tsx` - shadcn Select component (radix-ui/react-select based)
- `frontend/src/components/ui/table.tsx` - shadcn Table primitives (semantic HTML table)
- `frontend/src/pages/DashboardPage.tsx` - Extended with dimension state, isExporting state, useSpendBreakdown/useTopResources hooks, Cost Breakdown card, Top Resources card, handleExport function
- `frontend/src/pages/IngestionPage.tsx` - Auto-fixed pre-existing unused `prev` parameter in setStatus callback (renamed to `_prev`)

## Decisions Made

- Export button placed inline in Cost Breakdown card header next to the Select — keeps the action contextual to the data currently displayed
- Export uses `api` singleton directly rather than a hook — one-time imperative action, not server state; TanStack Query hooks are for declarative queries
- Both `dimension` and `days` params sent to `/costs/export` endpoint so the CSV filename is unambiguous (`cost-breakdown-service_name-30d.csv`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing unused `prev` parameter causing `tsc -b` build failure**
- **Found during:** Task 2 verification (npm run build)
- **Issue:** `IngestionPage.tsx` line 155 had `setStatus((prev) => {...})` where `prev` was declared but never read — the function used `data` from outer scope. TypeScript strict mode (TS6133) treats this as an error in `tsc -b`, causing `npm run build` to fail.
- **Fix:** Renamed `prev` to `_prev` — underscore prefix is the TypeScript convention for intentionally-unused parameters
- **Files modified:** `frontend/src/pages/IngestionPage.tsx`
- **Verification:** Confirmed error existed before any plan changes (git stash + build reproduced it); confirmed fixed after rename
- **Committed in:** `f17a813` (Task 1+2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - pre-existing bug)
**Impact on plan:** Fix was necessary for build verification requirement. Not scope creep — the error would have blocked `npm run build` verification for Task 2.

## Issues Encountered

- Pre-existing `TS6133: 'prev' is declared but its value is never read` error in IngestionPage.tsx blocked `npm run build`. Verified as pre-existing via `git stash` test, then fixed per deviation Rule 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 COST requirements (COST-01 through COST-06) are now implemented end-to-end
- Phase 3 has 1 remaining plan (03-05): human verification checkpoint
- Dashboard is fully functional for manual UAT: KPI cards, trend chart, cost breakdown with dimension selector, top resources, and CSV export all wired to live backend endpoints
- No blockers for Phase 4 (Anomaly Detection)

---
*Phase: 03-cost-monitoring*
*Completed: 2026-02-21*
