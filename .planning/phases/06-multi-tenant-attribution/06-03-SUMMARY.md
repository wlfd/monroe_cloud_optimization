---
phase: 06-multi-tenant-attribution
plan: "03"
subsystem: ui
tags: [react, tanstack-query, shadcn, typescript, attribution, csv-export]

# Dependency graph
requires:
  - phase: 06-02
    provides: Attribution API endpoints (/attribution/, /attribution/breakdown/{id}, /attribution/export, /settings/tenants, /settings/rules)

provides:
  - attribution.ts service hooks (4 query hooks, 6 mutation hooks, exportAttribution function)
  - AttributionPage with sortable table, expandable per-tenant breakdown rows, month/year pickers, Export CSV
  - SettingsPage with Tenants tab (inline name edit, acknowledge) and Allocation Rules tab (inline add, priority reorder, delete)
  - /attribution and /settings routes wired in App.tsx

affects:
  - 06-04 (frontend polish, end-to-end verification)
  - 06-05 (phase sign-off)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - TanStack Query hook pattern: interfaces at top, query hooks, mutation hooks with queryClient.invalidateQueries, standalone export functions last
    - Inline sub-component pattern: TenantBreakdownRow and AllocationRulesTab defined in same file as parent to co-locate mutation hooks and avoid prop drilling
    - Controlled inline editing: onMouseDown(preventDefault) on Save button prevents Input blur from firing before click handler

key-files:
  created:
    - frontend/src/services/attribution.ts
    - frontend/src/pages/AttributionPage.tsx
    - frontend/src/pages/SettingsPage.tsx
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "onMouseDown(e.preventDefault()) on Save button in inline editor prevents Input onBlur from firing and cancelling edit before save can execute"
  - "SortIndicator as inline function component (not extracted) keeps sort logic readable without adding a separate file"
  - "is_new field not present in TenantAttribution interface (only in TenantProfile) — UNALLOCATED row check uses tenant_id === 'UNALLOCATED' guard directly"

patterns-established:
  - "Blob download: responseType: blob + createObjectURL + link.click() + revokeObjectURL — consistent with cost.ts exportCostBreakdown"
  - "Client-side sort via [...items].sort() on 30-row table — no server-side sort param needed"
  - "Priority reorder: re-sort updated list by new priority, re-number 1..N, call reorder endpoint with ordered rule_ids"

requirements-completed: [ATTR-03, ATTR-04]

# Metrics
duration: 8min
completed: 2026-02-21
---

# Phase 6 Plan 03: Attribution Frontend Summary

**TanStack Query service hooks for attribution + Settings APIs, sortable/expandable AttributionPage table with month picker and CSV export, tabbed SettingsPage with inline tenant name editing and allocation rule CRUD**

## Performance

- **Duration:** 8 min
- **Started:** 2026-02-21T21:32:48Z
- **Completed:** 2026-02-21T21:40:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Created `attribution.ts` with 4 query hooks (useAttribution, useAttributionBreakdown, useTenantProfiles, useAllocationRules), 6 mutation hooks, and exportAttribution blob download function
- Built `AttributionPage.tsx` with sortable table (3 sort keys), expandable breakdown rows via TenantBreakdownRow, month/year pickers, New/Unallocated badges, and Export CSV
- Built `SettingsPage.tsx` with tabbed layout — TenantsTab (inline display name editing, acknowledge button) and AllocationRulesTab (inline add form, numbered priority editing, delete with confirm)
- Updated `App.tsx` to import and route `/attribution` and `/settings`, removing the placeholder comment block

## Task Commits

Each task was committed atomically:

1. **Task 1: Frontend service hooks (attribution.ts)** - `551faa8` (feat)
2. **Task 2: AttributionPage, SettingsPage, and App.tsx route wiring** - `8b14ed5` (feat)

## Files Created/Modified

- `frontend/src/services/attribution.ts` - All attribution/settings TanStack Query and mutation hooks plus exportAttribution
- `frontend/src/pages/AttributionPage.tsx` - Sortable attribution table with expandable rows, month picker, summary stats, CSV export
- `frontend/src/pages/SettingsPage.tsx` - Tabbed settings page with tenant management and allocation rule CRUD
- `frontend/src/App.tsx` - Added /attribution and /settings routes

## Decisions Made

- Used `onMouseDown(e.preventDefault())` on Save button in inline name editor to prevent Input's onBlur from cancelling the edit before the save click handler fires. This is the correct fix for the common "save before blur" React pattern.
- AllocationRulesTab uses numbered priority input (not drag-and-drop) per CONTEXT.md guidance — no new libraries needed.
- `is_new` field is in `TenantProfile` (not `TenantAttribution`) — the attribution table renders New badges via a type intersection cast for forward compatibility; UNALLOCATED guard uses `tenant_id === 'UNALLOCATED'` string comparison.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None — TypeScript compiled cleanly on first attempt for all three new files.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `/attribution` and `/settings` routes are fully wired and TypeScript-clean
- All service hooks are ready for end-to-end browser testing in Phase 06-04
- Sidebar Attribution and Settings nav links now resolve to real pages (requires sidebar to have those links already configured from prior phases)

---
*Phase: 06-multi-tenant-attribution*
*Completed: 2026-02-21*
