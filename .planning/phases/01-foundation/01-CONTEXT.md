# Phase 1: Foundation - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Deployable project skeleton: database, JWT authentication (email/password login, access + refresh tokens, logout), API infrastructure with OpenAPI docs at /api/docs, and a working React app shell. Engineers can deploy the application to Azure Container Apps and get a healthy status check. Everything future phases add (cost data, dashboards, anomaly detection) slots into this foundation.

</domain>

<decisions>
## Implementation Decisions

### Frontend scope
- App shell + routing — not just a login page; Phase 3+ features slot into a structure that already exists
- Sidebar nav + top bar layout: fixed left sidebar with nav links (Dashboard, Anomalies, Recommendations, Attribution, Settings) and a top bar with user info and logout
- After successful login, user lands at /dashboard showing a clear placeholder ("Dashboard coming in Phase 3") — establishes the route and layout without premature content
- Desktop-first — not optimizing for mobile in Phase 1; can be addressed later

### Claude's Discretion
- Token storage strategy (HttpOnly cookies vs localStorage) — choose what's most secure and clean given FastAPI + React setup
- First admin bootstrap approach (seed script, env var, or /setup endpoint) — whatever is simplest for a solo developer first-run experience
- Health check depth (/health endpoint contents — app-only vs DB/Redis ping)
- Login page polish and form UX details (validation feedback, password visibility toggle, etc.)

</decisions>

<specifics>
## Specific Ideas

- No specific references mentioned — open to standard shadcn/ui + Tailwind patterns for the shell

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-02-20*
