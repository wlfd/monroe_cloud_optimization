---
phase: 04-anomaly-detection
plan: "05"
subsystem: ui
tags: [react, tanstack-query, fastapi, anomaly-detection, ux]

# Dependency graph
requires:
  - phase: 04-anomaly-detection
    provides: Anomaly lifecycle endpoints (status PATCH, expected PATCH) and AnomaliesPage UI

provides:
  - Undo/revert capability for all three anomaly status-changing actions
  - Context-sensitive action buttons on AnomalyCard (status-aware rendering)
  - Backend support for reverting anomalies to "new" status
  - Backend unmark-expected endpoint (PATCH /expected with expected=false)
  - Phase 4 UAT human verification completed and signed off

affects: [05-recommendations, 06-attribution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Context-sensitive action buttons: render buttons based on current status/flag state rather than disabled/enabled
    - Toggle endpoint pattern: PATCH /{id}/expected accepts {expected: bool} to both mark and unmark with single endpoint

key-files:
  created: []
  modified:
    - backend/app/api/v1/anomaly.py
    - backend/app/services/anomaly.py
    - frontend/src/services/anomaly.ts
    - frontend/src/pages/AnomaliesPage.tsx

key-decisions:
  - "Context-sensitive action buttons (show/hide by status) preferred over disabled buttons — avoids confusion about what actions are possible"
  - "Toggle endpoint for expected flag: PATCH /{id}/expected accepts {expected: bool} — single endpoint for both mark and unmark instead of separate DELETE-style endpoint"
  - "Revert-to-new uses existing PATCH /{id}/status endpoint with status=new — just required adding new to _VALID_STATUSES whitelist"
  - "Phase 4 anomaly UAT signed off by human — all 8 verification steps passed with undo capability added as remediation"

patterns-established:
  - "Context-sensitive buttons: isNew/isInvestigating/isDismissed/isExpected flags drive which buttons render (not disabled state)"
  - "isMutating: combine all isPending flags across mutations — single disabled gate for all buttons on a card"

requirements-completed: [ANOMALY-01, ANOMALY-02, ANOMALY-03, ANOMALY-04]

# Metrics
duration: 15min
completed: 2026-02-21
---

# Phase 4 Plan 05: Anomaly Detection UAT Summary

**Anomaly lifecycle undo/revert UX: context-sensitive Revert to New and Unmark Expected buttons replacing always-disabled action buttons for dismissed and investigating states**

## Performance

- **Duration:** 15 min
- **Started:** 2026-02-21T10:15:00Z
- **Completed:** 2026-02-21T10:30:00Z
- **Tasks:** 1 (remediation + sign-off)
- **Files modified:** 4

## Accomplishments

- Human verification of Phase 4 completed — all 8 steps passed (anomalies page, severity, impact, filters, lifecycle, export, dashboard, detection config)
- User identified UX gap: no way to undo Investigate, Dismiss, or Mark as Expected actions
- Implemented context-sensitive action buttons: each status state shows only the appropriate undo/forward actions
- Backend extended to accept "new" as valid status (revert) and to toggle expected flag via single endpoint

## Task Commits

1. **Remediation: undo/revert buttons for all anomaly status actions** - `fe6b9a3` (feat)

**Plan metadata:** (final docs commit — see below)

## Files Created/Modified

- `backend/app/api/v1/anomaly.py` - Added "new" to _VALID_STATUSES; extended PATCH /{id}/expected to handle expected=false (unmark path); imported unmark_anomaly_expected
- `backend/app/services/anomaly.py` - Added unmark_anomaly_expected() function: clears expected=False, resets status="new", commits and refreshes
- `frontend/src/services/anomaly.ts` - Added useUnmarkAnomalyExpected hook (PATCH /expected with {expected: false}); updated useMarkAnomalyExpected to send explicit body
- `frontend/src/pages/AnomaliesPage.tsx` - Imported useUnmarkAnomalyExpected; rewrote AnomalyCard action button section with status-aware conditional rendering

## Decisions Made

- Context-sensitive buttons (show/hide by status) preferred over disabled buttons — clearer UX, avoids the "why is this greyed out?" confusion
- Single toggle endpoint for expected flag (`PATCH /{id}/expected` with `{expected: bool}`) rather than separate unmark endpoint — minimal API surface, consistent REST pattern
- Revert-to-new uses existing status endpoint (just required whitelisting "new") — no new endpoint needed
- isExpected badge label shows "Expected" when `expected=true` regardless of status — makes the flag visible at a glance

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Undo/revert capability for lifecycle actions**
- **Found during:** Human verification checkpoint
- **Issue:** User could not undo Investigate, Dismiss, or Mark as Expected — no way to revert to "new" status or clear expected flag
- **Fix:** Added context-sensitive buttons per status: Revert to New for investigating/dismissed, Unmark Expected for expected=true. Extended backend to accept status="new" and toggle expected=false.
- **Files modified:** backend/app/api/v1/anomaly.py, backend/app/services/anomaly.py, frontend/src/services/anomaly.ts, frontend/src/pages/AnomaliesPage.tsx
- **Verification:** TypeScript compiles clean (tsc --noEmit produces no output)
- **Committed in:** fe6b9a3

---

**Total deviations:** 1 (missing critical UX capability identified by human reviewer)
**Impact on plan:** Required but not planned. All 4 ANOMALY requirements now fully satisfied including correct lifecycle reversibility.

## Issues Encountered

None beyond the remediation item — backend and frontend wiring was straightforward.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 complete: anomaly detection, classification, lifecycle management, export, and dashboard integration all verified end-to-end
- All ANOMALY-01 through ANOMALY-04 requirements satisfied
- Ready for Phase 5: Recommendations

## Self-Check: PASSED

- FOUND: backend/app/api/v1/anomaly.py
- FOUND: backend/app/services/anomaly.py
- FOUND: frontend/src/services/anomaly.ts
- FOUND: frontend/src/pages/AnomaliesPage.tsx
- FOUND: .planning/phases/04-anomaly-detection/04-05-SUMMARY.md
- FOUND: commit fe6b9a3 (feat: undo/revert buttons)
- FOUND: commit c962cb7 (docs: plan complete)
- TypeScript: tsc --noEmit passed with no errors

---
*Phase: 04-anomaly-detection*
*Completed: 2026-02-21*
