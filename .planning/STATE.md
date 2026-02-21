# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** AI-powered optimization recommendations that identify savings Fileread actually implements
**Current focus:** Phase 2 - Data Ingestion

## Current Position

**Phase:** 2 of 7 (Data Ingestion)
**Current Plan:** Not started
**Total Plans in Phase:** 5
**Status:** Milestone complete
**Last Activity:** 2026-02-21

**Progress:** [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 8 (Plans 01-01 through 02-03 fully complete)
- Average duration: 9 min
- Total execution time: 58 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5 | 47 min | 12 min |
| 02-data-ingestion | 3 | 13 min | 4 min |

**Recent Trend:**
- Last 5 plans: 3 min, 25 min, 5 min, 2 min, 8 min
- Trend: API wiring (scheduler + endpoints) averages 8 min when service layer already established

*Updated after each plan completion*
| Phase 02 P03 | 8min | 2 tasks | 5 files |
| Phase 02-data-ingestion P04 | 15min | 2 tasks | 3 files |

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
- [Phase 02-data-ingestion]: scheduler.shutdown(wait=False) on FastAPI shutdown — avoids blocking shutdown for up to 4 hours if job in flight; asyncio.Lock handles in-flight concurrency
- [Phase 02-data-ingestion]: asyncio.create_task for manual /run trigger — fire-and-forget pattern keeps HTTP response immediate while ingestion runs in background
- [Phase 02-data-ingestion]: require_admin as a dependency function (not decorator) — composable with get_current_user, consistent with FastAPI DI patterns
- [Phase 02]: scheduler.shutdown(wait=False) on FastAPI shutdown — avoids blocking shutdown for up to 4 hours if job in flight; asyncio.Lock handles in-flight concurrency
- [Phase 02-data-ingestion]: No dismiss button on alert banner — auto-clears on next successful run per locked decision INGEST-05
- [Phase 02-data-ingestion]: Admin nav items in separate adminNavItems array (not mixed into navItems) — keeps standard nav stable per locked sidebar decision
- [Phase 02-data-ingestion]: 5-second polling interval cleared via useRef on unmount — prevents memory leaks and phantom API calls after navigation

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** 2026-02-21T01:26:09.331Z
**Stopped at:** Completed 02-04-PLAN.md — IngestionPage, App.tsx route, AppSidebar admin nav link, human verification passed
**Resume file:** None
