---
phase: 04-anomaly-detection
plan: "04"
subsystem: ui
tags: [react, tanstack-query, shadcn-ui, typescript, anomaly-detection]

# Dependency graph
requires:
  - phase: 04-anomaly-detection (plan 03)
    provides: anomaly service hooks (useAnomalies, useAnomalySummary, useUpdateAnomalyStatus, useMarkAnomalyExpected, exportAnomalies), Badge component, /anomalies route wired

provides:
  - Full AnomaliesPage with card-list UI, 4 KPI cards, filter dropdowns, action buttons, export, detection config panel
  - Dashboard Active Anomalies KPI card with worst-severity label and link to /anomalies
  - 4-column KPI grid on Dashboard

affects:
  - 05-recommendations (pattern: full page with KPI row + card list + filter row)
  - 06-attribution (pattern: same)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Dual useAnomalies calls: one unfiltered for filter-option derivation, one filtered for display"
    - "Worst-severity label: critical_count > 0 => red, else high_count > 0 => orange, else medium_count > 0 => blue"
    - "AnomalyCard as inline sub-component in same file — keeps mutations co-located with render"
    - "exportAnomalies one-off action (not a hook) for CSV download — consistent with Phase 3 export pattern"

key-files:
  created:
    - frontend/src/pages/AnomaliesPage.tsx
  modified:
    - frontend/src/pages/DashboardPage.tsx

key-decisions:
  - "Dual useAnomalies() calls in AnomaliesPage: unfiltered for filter-option derivation, filtered for display — avoids separate /filter-options endpoint call from page layer"
  - "Worst-severity label on Dashboard Active Anomalies card: shows highest-priority count (Critical in red, High in orange, Medium in blue) when active_count > 0"
  - "toLocaleDateString() used instead of date-fns for date formatting — date-fns not in project dependencies"
  - "AnomalyCard sub-component defined inline in AnomaliesPage.tsx — keeps mutation hooks co-located with card render, avoids prop-drilling update/mark callbacks"

patterns-established:
  - "Page structure: header row (title + action button) -> KPI grid -> filter row -> section header with summary -> card list (skeleton/empty/data) -> config panel"
  - "Worst-severity label pattern: ternary chain on critical_count/high_count/medium_count — reusable in any severity-aware KPI card"

requirements-completed: [ANOMALY-04]

# Metrics
duration: 12min
completed: 2026-02-21
---

# Phase 4 Plan 04: Anomaly Detection UI Summary

**Full AnomaliesPage with severity-dot card list, 4 KPI cards, filter dropdowns, and action buttons; Dashboard updated to 4-column KPI grid with Active Anomalies card showing worst-severity label**

## Performance

- **Duration:** 12 min
- **Started:** 2026-02-21T10:04:23Z
- **Completed:** 2026-02-21T10:16:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- AnomaliesPage: 380-line component with colored severity dots, status badges, action buttons (Investigate/Dismiss/Mark as Expected/View Resources), estimated impact in red, export, and detection config panel
- Dashboard updated: 4-column KPI grid, Active Anomalies card with count in red when >0, worst-severity label (e.g. "1 Critical" in red, "3 High" in orange, "2 Medium" in blue), "View anomalies" link
- Zero TypeScript compilation errors introduced — clean compile throughout

## Task Commits

Each task was committed atomically:

1. **Task 1: Build AnomaliesPage.tsx** - `b0657ac` (feat)
2. **Task 2: Update DashboardPage KPI grid with anomaly card** - `ff7edb5` (feat)

## Files Created/Modified
- `frontend/src/pages/AnomaliesPage.tsx` - Full anomaly detection page (380 lines): KPI summary cards, filter dropdowns for Service/Resource Group/Severity, AnomalyCard sub-component with mutations wired, export handler, detection config panel
- `frontend/src/pages/DashboardPage.tsx` - Added Active Anomalies KPI card, updated grid to lg:grid-cols-4, imported useAnomalySummary and Link

## Decisions Made
- Dual `useAnomalies()` calls: one unfiltered for filter-option derivation, one filtered for display. Avoids a separate API call while keeping filter options stable as user applies filters.
- `toLocaleDateString()` used for date formatting since `date-fns` is not in project dependencies.
- Worst-severity label implemented as requested by plan checker: ternary chain checks `critical_count > 0` first (red), then `high_count > 0` (orange), then `medium_count` (blue). Only shown when `active_count > 0`.
- AnomalyCard defined as inline sub-component in the same file — keeps mutation hooks co-located with the card render without prop-drilling.

## Deviations from Plan

None - plan executed exactly as written, plus the plan-checker's additional note (worst-severity label on Dashboard card) was incorporated as specified.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AnomaliesPage and Dashboard anomaly card are complete and TypeScript-clean
- Phase 5 (Recommendations) can use the same page structure pattern: header + KPI row + filter row + card list + config panel
- Anomaly lifecycle (Investigate/Dismiss/Mark as Expected) fully wired to backend mutations from Phase 4 Plan 02/03

---
*Phase: 04-anomaly-detection*
*Completed: 2026-02-21*
