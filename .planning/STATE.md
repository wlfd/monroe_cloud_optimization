# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** AI-powered optimization recommendations that identify savings Fileread actually implements
**Current focus:** Phase 1 - Foundation

## Current Position

Phase: 1 of 7 (Foundation)
Plan: 3 of 5 in current phase
Status: In progress
Last activity: 2026-02-20 — Completed 01-03 (React frontend: Vite + shadcn/ui auth shell, login page, authenticated layout)

Progress: [███░░░░░░░] 15%

## Performance Metrics

**Velocity:**
- Total plans completed: 3
- Average duration: 14 min
- Total execution time: 42 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 3 | 42 min | 14 min |

**Recent Trend:**
- Last 5 plans: 15 min, 2 min, 25 min
- Trend: Frontend scaffold heavier than auth API due to tooling setup (shadcn/ui preflight)

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Modular monolith over microservices — solo developer + April 2026 deadline; ships faster, easier to debug
- Azure OpenAI primary, Anthropic Claude fallback — same tenant for lower latency; fallback prevents lock-in
- Read-only recommendations for MVP — no auto-execution; trust must be established first
- Tag-based attribution — Fileread consistently tags resources with `tenant_id`; direct mapping works
- PyJWT (import jwt) not python-jose — python-jose abandoned; FastAPI docs updated to recommend PyJWT
- pwdlib[argon2] not passlib — passlib unmaintained, breaks Python 3.12+; pwdlib is FastAPI-recommended replacement
- Admin bootstrap via env vars (FIRST_ADMIN_EMAIL + FIRST_ADMIN_PASSWORD) — simplest for solo developer first-run
- docs_url="/api/docs" in FastAPI() constructor directly — NOT via router prefix — prevents 404
- Cookie path scoped to /api/v1/auth — reduces CSRF attack surface vs path=/
- JWT type claim ('access'/'refresh') enforced at decode time — prevents token misuse across endpoints
- oauth2_scheme tokenUrl=/api/v1/auth/login — FastAPI auto-generates OAuth2 lock icons in Swagger UI
- Access token in module-level memory (never localStorage) — XSS protection; HttpOnly cookie for refresh token
- useAuth file uses .tsx extension (not .ts) — contains JSX (AuthContext.Provider) requiring JSX transform
- Sidebar locked to 5 nav items: Dashboard, Anomalies, Recommendations, Attribution, Settings (LOCKED DECISION)
- shadcn/ui paths alias must be in both tsconfig.json and tsconfig.app.json — shadcn preflight reads root tsconfig

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 01-03-PLAN.md (React frontend: Vite + shadcn/ui, auth shell, login page, dashboard placeholder)
Resume file: None
