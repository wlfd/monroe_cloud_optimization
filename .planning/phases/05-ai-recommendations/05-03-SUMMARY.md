---
phase: 05-ai-recommendations
plan: "03"
subsystem: frontend
tags: [react, tanstack-query, recommendations, ui]
dependency_graph:
  requires: [05-02]
  provides: [recommendations-ui, recommendation-service-hooks]
  affects: [frontend/src/App.tsx]
tech_stack:
  added: []
  patterns:
    - TanStack Query hooks for recommendations (follows anomaly.ts pattern)
    - Inline card component with sub-components (follows AnomaliesPage pattern)
    - Admin-gated action button using useAuth role check
key_files:
  created:
    - frontend/src/services/recommendation.ts
    - frontend/src/pages/RecommendationsPage.tsx
  modified:
    - frontend/src/App.tsx
decisions:
  - No Apply/Dismiss/Accept buttons on recommendation cards — deferred to v2 per locked plan decision
  - No cache/date indicators on cards — invisible per locked plan decision
  - Inline comparison panel (current → recommended) matches reference design
metrics:
  duration: 2min
  completed: 2026-02-21
---

# Phase 5 Plan 03: Recommendations Frontend Summary

**One-liner:** Full /recommendations page with TanStack Query service hooks, card list UI with current→recommended comparison panels, filter bar, summary stat row, daily limit banner, and empty state with admin trigger button.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Recommendation service hooks (TanStack Query) | 4531f79 | frontend/src/services/recommendation.ts |
| 2 | RecommendationsPage and App.tsx route wiring | 6b36f62 | frontend/src/pages/RecommendationsPage.tsx, frontend/src/App.tsx |

## What Was Built

### Task 1: recommendation.ts

Service layer following the anomaly.ts pattern exactly:

- `Recommendation` interface with full field set including `category` union type (`'right-sizing' | 'idle' | 'reserved' | 'storage'`)
- `RecommendationSummary` interface with `daily_limit_reached`, `calls_used_today`, `daily_call_limit` fields
- `RecommendationFilters` interface for category, min_savings, min_confidence
- `useRecommendations(filters)` hook — 5-min staleTime, filters empty/undefined/zero/all values before sending params
- `useRecommendationSummary()` hook — 5-min staleTime
- `triggerRecommendations()` one-off async function (not a hook)

### Task 2: RecommendationsPage.tsx + App.tsx

Full recommendations page:

1. **Summary stat row** — 6-column grid: Potential Monthly Savings (highlighted green), Total count, plus Right-Sizing / Idle / Reserved / Storage category counts
2. **Daily limit banner** — `Alert` component, conditional on `summaryData?.daily_limit_reached`
3. **Filter bar** — Type (all/right-sizing/idle/reserved/storage), Min Savings (any/$100+/$500+/$1000+), Confidence (any/70+/80+/90+) dropdowns
4. **Card list** — `RecommendationCard` sub-component with:
   - Resource name + resource group header
   - Category badge (color-coded) + confidence badge (high/medium/low)
   - Current → Recommended comparison panel with `ArrowRight` icon
   - Savings line (green) + confidence % line
   - Inline LLM explanation (always visible, no expand/collapse)
5. **Loading state** — 3 `RecommendationSkeleton` cards
6. **Empty state** — message + `Generate Recommendations` button gated on `user?.role === 'admin'`

App.tsx updated: import added + `/recommendations` route wired to `RecommendationsPage`.

## Verification

All 7 plan verification checks passed:

1. `tsc --noEmit` — no errors
2. `grep "RecommendationsPage" App.tsx` — 2 lines (import + route element)
3. All 3 hooks imported and used in RecommendationsPage.tsx
4. `daily_limit_reached` used in limit banner
5. `ArrowRight` + comparison panel present
6. `Generate Recommendations` button in empty state
7. No Apply/Dismiss/Accept buttons on cards (v2 deferred)

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check

Files created/modified:
- frontend/src/services/recommendation.ts
- frontend/src/pages/RecommendationsPage.tsx
- frontend/src/App.tsx

Commits:
- 4531f79 — feat(05-03): add recommendation service hooks (TanStack Query)
- 6b36f62 — feat(05-03): add RecommendationsPage and wire /recommendations route

## Self-Check: PASSED

All files exist and all commits verified.
