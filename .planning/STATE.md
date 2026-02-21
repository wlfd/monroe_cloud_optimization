# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** AI-powered optimization recommendations that identify savings Fileread actually implements
**Current focus:** Phase 2 - Data Ingestion

## Current Position

Phase: 2 of 7 (Data Ingestion)
Plan: 3 of 5 in current phase (02-02 complete — azure_client.py + ingestion.py built)
Status: Phase 2 plan 02 complete; ready for 02-03 (Scheduler + Ingestion API endpoints)
Last activity: 2026-02-20 — Completed 02-02 — Azure Cost Management client, ingestion orchestration service

Progress: [████░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 7 (Plans 01-01 through 02-02 fully complete)
- Average duration: 9 min
- Total execution time: 50 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5 | 47 min | 12 min |
| 02-data-ingestion | 2 | 5 min | 2.5 min |

**Recent Trend:**
- Last 5 plans: 2 min, 3 min, 25 min, 5 min, 2 min
- Trend: Service layer implementation is fast (3 min) when models + config established by prior plan

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
- [Phase 01-foundation]: Multi-stage frontend Dockerfile with target:builder in docker-compose — single Dockerfile serves dev (node) and production (nginx)
- [Phase 01-foundation]: Health probe path is /api/v1/health not /health — routes registered under /api/v1 prefix in FastAPI main.py
- [Phase 02-data-ingestion]: AZURE_SUBSCRIPTION_SCOPE as plain empty-string field — ingestion service computes /subscriptions/{ID} at runtime (avoids pydantic model_validator complexity)
- [Phase 02-data-ingestion]: MOCK_AZURE bool flag in Settings allows local dev without real Azure credentials
- [Phase 02-data-ingestion]: utcnow() helper redefined per model file (billing.py, user.py) — keeps model files decoupled, no cross-file imports
- [Phase 02-data-ingestion]: 24h overlap applied to delta window start — catches late-arriving Azure records (Pattern 6 from research)
- [Phase 02-data-ingestion]: get_settings() called at function-call time in services (not module-level) — required for test cache invalidation
- [Phase 02-data-ingestion]: AsyncSessionLocal used directly in service layer — scheduler jobs run outside request context (Pattern 7)
- [Phase 02-data-ingestion]: Fresh error session opened in _do_ingestion exception handler — avoids using dirty/rolled-back session for error logging

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-20
Stopped at: Completed 02-02-PLAN.md — azure_client.py (fetch, retry, mock) + ingestion.py (orchestration, delta window, upsert, backfill, alerts, run logging)
Resume file: None — advance to 02-03
