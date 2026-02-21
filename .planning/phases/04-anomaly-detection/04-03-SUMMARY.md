---
phase: 04-anomaly-detection
plan: "03"
subsystem: ui
tags: [react, tanstack-query, shadcn, typescript, axios]

# Dependency graph
requires:
  - phase: 04-anomaly-detection (plan 02)
    provides: Backend anomaly API endpoints (/anomalies/, /anomalies/summary, /anomalies/{id}/status, /anomalies/{id}/expected, /anomalies/export)
provides:
  - TanStack Query hooks for all anomaly API endpoints (useAnomalies, useAnomalySummary, useUpdateAnomalyStatus, useMarkAnomalyExpected)
  - TypeScript interfaces (Anomaly, AnomalySummary, AnomalyFilters) matching backend Pydantic schemas
  - exportAnomalies() CSV blob download function
  - shadcn Badge component available in frontend/src/components/ui/badge.tsx
  - /anomalies route wired in App.tsx pointing to AnomaliesPage
  - Minimal AnomaliesPage.tsx stub (replaced by Plan 04)
affects: [04-04, 04-05]

# Tech tracking
tech-stack:
  added: [shadcn Badge component]
  patterns:
    - useQuery with staleTime=2min for anomaly data (shorter than cost's 5min — anomaly data more time-sensitive)
    - useMutation with dual queryClient.invalidateQueries (both anomalies list and anomaly-summary) on mutation success
    - exportAnomalies as plain async function (not a hook) — one-time action, not server state (follows Phase 3 precedent)
    - Filter params cleaned via Object.fromEntries + .filter to strip undefined/empty/'all' before passing to API

key-files:
  created:
    - frontend/src/services/anomaly.ts
    - frontend/src/components/ui/badge.tsx
    - frontend/src/pages/AnomaliesPage.tsx
  modified:
    - frontend/src/App.tsx

key-decisions:
  - "AnomaliesPage.tsx stub created to resolve import before Plan 04 builds the full component — avoids TS compilation errors"

patterns-established:
  - "Anomaly service structure follows cost.ts exactly: interfaces at top, useQuery hooks, useMutation hooks, standalone functions last"

requirements-completed: [ANOMALY-04]

# Metrics
duration: 1min
completed: 2026-02-21
---

# Phase 4 Plan 03: Anomaly Service Summary

**TanStack Query data layer for anomaly detection with shadcn Badge, typed hooks for all 4 anomaly endpoints, and /anomalies route wired in React Router**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-21T10:02:05Z
- **Completed:** 2026-02-21T10:02:30Z
- **Tasks:** 1
- **Files modified:** 4

## Accomplishments
- shadcn Badge component installed and available for Plan 04's AnomaliesPage UI
- Complete anomaly.ts service with all 4 hooks and exportAnomalies function, fully typed with TypeScript interfaces matching backend Pydantic schemas
- /anomalies route wired in App.tsx with minimal stub page; TypeScript compilation: 0 errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Install shadcn Badge, create anomaly.ts service hooks, wire App.tsx route** - `da1de86` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `frontend/src/services/anomaly.ts` - All TanStack Query hooks and TypeScript interfaces for anomaly API
- `frontend/src/components/ui/badge.tsx` - shadcn Badge component (installed via npx shadcn add badge)
- `frontend/src/pages/AnomaliesPage.tsx` - Minimal stub page (replaced by Plan 04 full implementation)
- `frontend/src/App.tsx` - Added AnomaliesPage import and /anomalies route

## Decisions Made
- AnomaliesPage.tsx stub created before Plan 04 to allow TypeScript compilation without errors while the route is wired — Plan 04 replaces this file entirely.
- staleTime set to 2 minutes for anomaly hooks (vs 5 minutes for cost hooks) — anomaly status changes are more time-sensitive and should reflect updates sooner.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- anomaly.ts service layer is complete and importable by Plan 04's AnomaliesPage
- shadcn Badge component ready for severity/status badge rendering in the UI
- /anomalies route active — navigation will reach AnomaliesPage once Plan 04 replaces the stub

---
*Phase: 04-anomaly-detection*
*Completed: 2026-02-21*
