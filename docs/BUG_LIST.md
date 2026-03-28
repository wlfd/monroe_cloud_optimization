# CloudCost -- Bug List and Resolution Report

**Course:** CS 701 -- Special Projects in Computer Science
**Project:** CloudCost Azure Cloud Cost Optimization SaaS Platform
**Stack:** FastAPI (Python 3.12) + React 19 / TypeScript + PostgreSQL 15
**Author:** Monroe Cloud Optimization Team
**Date:** March 27, 2026

---

## Purpose

This document provides a formal record of all bugs identified, triaged, and resolved during the development of the CloudCost platform. Each entry includes a root cause analysis and the specific resolution applied. The report serves as both a project deliverable for CS 701 and a reference for future maintenance.

---

## Summary

| Metric              | Count |
|---------------------|-------|
| Total Bugs Tracked  | 9     |
| Resolved            | 9     |
| Open                | 0     |

---

## Bug Register

| ID       | Description                                | Category        | Status   | Date Resolved |
|----------|--------------------------------------------|-----------------|----------|---------------|
| BUG-001  | CI test failures (frontend)                | Testing / CI    | Resolved | 2026-03-27    |
| BUG-002  | GitGuardian secret detection flag          | Security / CI   | Resolved | 2026-03-27    |
| BUG-003  | Manual seed required after compose up      | DevEx           | Resolved | 2026-03-27    |
| BUG-004  | Date timezone off-by-one                   | Frontend / UX   | Resolved | 2026-03-14    |
| BUG-005  | Array index used as React key              | Frontend / UX   | Resolved | 2026-03-14    |
| BUG-006  | 7 security vulnerabilities                 | Security        | Resolved | 2026-03-14    |
| BUG-007  | HTML5 drag events unreliable for reorder   | Frontend / UX   | Resolved | 2026-02-21    |
| BUG-008  | Missing Alert UI component                 | Frontend        | Resolved | 2026-02-21    |
| BUG-009  | Leftover code reference                    | Frontend        | Resolved | 2026-02-21    |

---

## Detailed Entries

### BUG-001: CI Test Failures (Frontend)

- **Date:** 2026-03-27
- **Status:** Resolved
- **Description:** Multiple frontend test suites crashed during CI runs, specifically DashboardPage and AnomaliesPage tests.
- **Root Cause:** The jsdom test environment lacks native implementations of `ResizeObserver` (required by Recharts charting library) and pointer-capture APIs (required by Radix UI primitives). Additionally, the LoginPage test matched an ambiguous `aria-label`, and React 19 async work leaked state between test cases.
- **Resolution:**
  - Mocked `ResizeObserver` and pointer-capture APIs in the global test setup (`setup.ts`).
  - Switched to exact string matching for `aria-label` selectors.
  - Reordered test cases to prevent state pollution across suites.
  - Added controlled server response delays for loading-state assertions.

---

### BUG-002: GitGuardian Secret Detection Flag

- **Date:** 2026-03-27
- **Status:** Resolved
- **Description:** GitGuardian flagged a JWT placeholder value in `docker-compose.yml` as a leaked generic secret.
- **Root Cause:** The default value assigned to `JWT_SECRET_KEY` matched GitGuardian's heuristic pattern for generic high-entropy secrets.
- **Resolution:** Renamed the JWT placeholder to a value that does not trigger the pattern match while remaining clearly identifiable as a non-production default.

---

### BUG-003: Developer Experience -- Manual Seed Required

- **Date:** 2026-03-27
- **Status:** Resolved
- **Description:** After running `docker compose up`, new developers had to manually execute the admin seed script before they could log in.
- **Root Cause:** The `docker-compose.yml` file did not include an automatic seeding step.
- **Resolution:** Added a dedicated `seed` service to `docker-compose.yml` that runs automatically after the migration service completes. Set `MOCK_AZURE=true` by default so no external Azure credentials are required for local development.

---

### BUG-004: Date Timezone Off-by-One

- **Date:** 2026-03-14
- **Status:** Resolved
- **Description:** Date values displayed one day behind the expected date for users located west of UTC.
- **Root Cause:** Bare date strings (e.g., `"2026-03-13"`) passed to the JavaScript `Date` constructor are parsed as UTC midnight per the ECMAScript specification. When `toLocaleDateString()` converts to a negative-offset timezone, the displayed date shifts backward by one day.
- **Resolution:** Appended `"T00:00:00"` to date strings before constructing `Date` objects, causing them to be parsed as local midnight rather than UTC midnight.

---

### BUG-005: Array Index Used as React Key

- **Date:** 2026-03-14
- **Status:** Resolved
- **Description:** The Cost Breakdown and Top Resources tables exhibited incorrect DOM reconciliation when rows were sorted or reordered.
- **Root Cause:** Both tables used `key={idx}` (the array index) instead of stable, data-driven identifiers. This caused React to incorrectly reuse DOM nodes after reorder operations.
- **Resolution:** Replaced index-based keys with stable identifiers: `item.dimension_value` for the Cost Breakdown table and `resource.resource_id` for the Top Resources table.

---

### BUG-006: 7 Security Vulnerabilities

- **Date:** 2026-03-14
- **Status:** Resolved
- **Description:** A systematic architecture security review identified seven vulnerabilities across the backend and API layer.
- **Root Cause and Resolution (per finding):**

| Finding  | Issue                                                    | Resolution                                                        |
|----------|----------------------------------------------------------|-------------------------------------------------------------------|
| CRIT-05  | Webhook HMAC secret exposed in API responses             | Redacted secret fields from all API response schemas              |
| CRIT-06  | Brute-force login lockout logic was dead code            | Wired lockout enforcement (5 failed attempts triggers 15min lock) |
| CRIT-02  | `session.rollback()` corrupted shared session in budget check loop | Switched to per-iteration database sessions                |
| CRIT-01  | Anthropic client instantiated before API key guard       | Moved client construction to after the API key validation check   |
| SEC-02   | Refresh tokens never expired server-side                 | Added `expires_at` check on refresh token validation              |
| SEC-03   | Default JWT secret accepted in production mode           | Added startup validation that rejects default secrets in production |
| API-04   | IDOR on budget threshold deletion endpoint               | Added ownership verification before allowing deletion             |

---

### BUG-007: HTML5 Drag Events Unreliable for Rule Reorder

- **Date:** 2026-02-21
- **Status:** Resolved
- **Description:** The allocation rule drag-to-reorder feature did not work reliably across browsers.
- **Root Cause:** Three compounding issues: (1) `handleDragStart` did not receive a `DragEvent` parameter, so `effectAllowed` was never set; (2) pointer movement over child table cells and buttons swallowed `onDragOver` events; (3) the `GripVertical` SVG icon intercepted pointer events, preventing the drag handle from receiving them.
- **Resolution:** Replaced the HTML5 Drag and Drop API with a pointer-event-based implementation (`pointermove` + `getBoundingClientRect` for hit testing). Applied `pointer-events: none` to the grip icon. Added a catch-all `onDragOver` handler on the `TableBody` element.

---

### BUG-008: Missing Alert Component

- **Date:** 2026-02-21
- **Status:** Resolved
- **Description:** The RecommendationsPage imported and rendered an `Alert` component that did not exist in the project's UI library.
- **Root Cause:** The component was referenced in code but was never added to the shadcn/ui component set during initial setup.
- **Resolution:** Replaced the missing `Alert` component with an inline `div` banner element styled to serve the same purpose.

---

### BUG-009: Leftover Code Reference

- **Date:** 2026-02-21
- **Status:** Resolved
- **Description:** The anomaly section header referenced a `summaryParts` variable that no longer existed.
- **Root Cause:** The `summaryParts` variable was removed during a prior refactor, but a reference to it was left behind in the template.
- **Resolution:** Removed the stale variable reference.

---

## Lessons Learned

1. **Systematic security review pays off.** BUG-006 encompassed seven distinct vulnerabilities, several of which (HMAC secret exposure, IDOR, dead lockout code) would have been difficult to catch through normal feature testing. Conducting a dedicated architecture-level security audit before release proved essential.

2. **Cross-browser and cross-environment testing is non-negotiable.** BUG-007 (HTML5 drag unreliability) and BUG-001 (jsdom missing APIs) both stemmed from assuming consistent behavior across environments. Testing in multiple browsers and validating that the CI test environment faithfully represents runtime behavior should be standard practice.

3. **Timezone-aware date handling requires explicit construction.** BUG-004 demonstrated that JavaScript's `Date` constructor has subtle UTC-vs-local parsing rules that vary by input format. Establishing a project-wide convention for date construction (always specifying a time component) prevents an entire class of off-by-one display bugs.

4. **React key selection matters for correctness, not just performance.** BUG-005 showed that index-based keys produce visually incorrect results when data is reordered. Using stable, data-derived keys should be enforced through linting or code review.

5. **Developer experience is a reliability concern.** BUG-003 (manual seeding) created a friction point where new contributors could not run the application out of the box. Automating setup steps in `docker-compose.yml` reduces onboarding errors and ensures a consistent development environment.

6. **CI pipeline hygiene requires ongoing attention.** BUG-002 (GitGuardian false positive) highlighted that secret-scanning tools use pattern heuristics that can flag placeholder values. Choosing default values that are clearly non-secret (and do not match high-entropy patterns) avoids unnecessary CI failures and alert fatigue.
