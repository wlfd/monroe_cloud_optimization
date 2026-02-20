---
phase: 01-foundation
plan: "04"
subsystem: infra
tags: [docker, docker-compose, nginx, github-actions, ci, pytest, ruff, vite, multi-stage-build]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: backend Dockerfile stub, docker-compose stub, FastAPI app, migrations
  - phase: 01-foundation/01-02
    provides: auth endpoints at /api/v1/auth/*
  - phase: 01-foundation/01-03
    provides: React frontend, frontend Dockerfile stub

provides:
  - Production-grade backend/Dockerfile with python:3.12-slim, libpq-dev, HEALTHCHECK, --proxy-headers
  - Multi-stage frontend/Dockerfile (node:20-slim builder + nginx:alpine serve); target:builder for dev
  - frontend/nginx.conf with SPA routing fallback and /api/ reverse proxy for production
  - docker-compose.yml with migrate service, healthchecks on all services, proper service dependencies
  - docker-compose.prod.yml with production overrides (2 workers, no bind mounts)
  - .env.example with all required variables and comments
  - .github/workflows/test.yml CI: pytest+ruff (backend) and tsc+build (frontend)
  - backend/tests/conftest.py Phase 1 test scaffold with event_loop fixture
  - README.md quick-start guide covering env setup, docker compose up, seed admin, access URLs

affects: [02-ingestion, 03-analysis, all-subsequent-phases]

# Tech tracking
tech-stack:
  added:
    - nginx:alpine (production frontend serving)
    - GitHub Actions CI (actions/checkout@v4, actions/setup-python@v5, actions/setup-node@v4)
    - ruff (Python linter in CI)
    - pytest (test runner stub)
  patterns:
    - Multi-stage Docker build: node:20-slim builder target for dev, nginx:alpine for prod
    - docker-compose target:builder — dev services use node stage, production uses nginx stage
    - Migrate-first pattern: separate migrate service with service_completed_successfully dependency
    - Health probe path: /api/v1/health (not /health — routes are under /api/v1 prefix)
    - docker-compose env_file with required:false — .env.local is optional override, never committed

key-files:
  created:
    - backend/Dockerfile
    - frontend/Dockerfile
    - frontend/nginx.conf
    - docker-compose.yml
    - docker-compose.prod.yml
    - .env.example
    - .github/workflows/test.yml
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - README.md
  modified: []

key-decisions:
  - "frontend/Dockerfile multi-stage with target:builder in docker-compose — allows npm run dev in dev, nginx serve in prod from same Dockerfile"
  - "Health probe path is /api/v1/health not /health — all routes are under /api/v1 prefix per main.py setup"
  - "HEALTHCHECK in Dockerfile uses /api/v1/health — matches actual route registration (Dockerfile updated from plan spec)"
  - "docker-compose uses env_file with required:false — .env.local optional override, secrets not committed"
  - "CI uses ruff for linting (ruff check app/) installed as separate step in CI to keep requirements.txt lean"

patterns-established:
  - "Migrate-first: docker-compose has separate migrate service with service_completed_successfully condition before api starts"
  - "docker-compose target: frontend service uses target:builder (node) for dev, production Dockerfile uses nginx stage"

requirements-completed: [API-02, API-03]

# Metrics
duration: 5min
completed: 2026-02-20
---

# Phase 1 Plan 04: Docker, CI, README Summary

**Production-grade Dockerfiles with multi-stage frontend build, full docker-compose stack (db/redis/migrate/api/frontend) with healthchecks and service ordering, GitHub Actions CI (pytest+ruff+tsc+build), and README quick-start guide**

## Performance

- **Duration:** 5 minutes
- **Started:** 2026-02-20T18:01:52Z
- **Completed:** 2026-02-20T18:07:15Z
- **Tasks:** 1 auto + 1 checkpoint (pending human verification)
- **Files modified:** 10

## Accomplishments

- Backend Dockerfile upgraded to production-grade: python:3.12-slim with libpq-dev, HEALTHCHECK on /api/v1/health, --proxy-headers for Azure Container Apps TLS termination
- Frontend Dockerfile refactored to multi-stage build (node:20-slim builder + nginx:alpine serve); docker-compose uses target:builder so dev server runs npm run dev while production uses nginx
- docker-compose.yml rebuilt with migrate service (alembic upgrade head before API starts), healthchecks on db/redis/api, proper service_completed_successfully and service_healthy dependency conditions
- GitHub Actions CI with two parallel jobs: backend (ruff lint + alembic migrations + pytest) and frontend (tsc --noEmit + vite build) running on push/PR to main
- Stack verified running: db/redis healthy, migrate exits 0, api healthy, frontend 200, auth flow end-to-end working

## Task Commits

1. **Task 1: Production Dockerfiles, docker-compose, CI, README** - `722b524` (feat)

**Task 2 (checkpoint) awaiting human verification.**

## Files Created/Modified

- `backend/Dockerfile` - python:3.12-slim, libpq-dev, HEALTHCHECK at /api/v1/health, --proxy-headers
- `frontend/Dockerfile` - multi-stage: node:20-slim builder (target for dev) + nginx:alpine serve (production)
- `frontend/nginx.conf` - SPA try_files fallback + /api/ proxy_pass to backend
- `docker-compose.yml` - migrate service, healthchecks, service_healthy/completed_successfully dependencies
- `docker-compose.prod.yml` - uvicorn 2 workers, no bind mounts, APP_ENV=production
- `.env.example` - all env vars with section comments
- `.github/workflows/test.yml` - backend (ruff + alembic + pytest) and frontend (tsc + build) CI jobs
- `backend/tests/__init__.py` - empty package marker
- `backend/tests/conftest.py` - Phase 1 pytest scaffold with event_loop fixture
- `README.md` - quick-start: copy .env, docker compose up, seed admin, access URLs

## Decisions Made

- **Multi-stage frontend Dockerfile with target:builder in docker-compose:** Single Dockerfile serves both dev (node stage) and production (nginx stage). docker-compose specifies `target: builder` so dev server can run `npm run dev`; CI and production deployments use the full Dockerfile to get the nginx stage.
- **HEALTHCHECK path corrected to /api/v1/health:** Plan spec used `/health` but all routes are registered under `/api/v1` prefix via `app.include_router(api_router, prefix="/api/v1")` in main.py. Updated both Dockerfile HEALTHCHECK and docker-compose healthcheck.
- **ruff installed inline in CI:** Not in requirements.txt to keep the runtime image lean. CI installs it with `pip install ruff` in a dedicated step.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Frontend Dockerfile command override incompatibility**
- **Found during:** Task 1 (docker-compose.yml creation)
- **Issue:** Plan's docker-compose.yml used `command: npm run dev -- --host 0.0.0.0` with the multi-stage Dockerfile, but the final nginx image doesn't have npm/node available. Running npm on an nginx container would fail.
- **Fix:** Added `target: builder` to the frontend build config in docker-compose.yml so the dev compose stack uses the node stage (which has npm), while production uses the full multi-stage build.
- **Files modified:** `docker-compose.yml` (added `target: builder` to frontend service build config)
- **Verification:** `docker compose build` succeeded, frontend container started with npm run dev at localhost:3000 (HTTP 200)
- **Committed in:** 722b524 (Task 1 commit)

**2. [Rule 1 - Bug] Healthcheck URL mismatched route registration**
- **Found during:** Task 1 verification
- **Issue:** Plan spec used `/health` in HEALTHCHECK and docker-compose healthcheck, but the actual routes are at `/api/v1/health` (FastAPI app registers api_router with `prefix="/api/v1"`). API was showing `(unhealthy)` in docker compose ps.
- **Fix:** Updated backend/Dockerfile HEALTHCHECK CMD to use `http://localhost:8000/api/v1/health` and updated docker-compose.yml api healthcheck to the same URL.
- **Files modified:** `backend/Dockerfile`, `docker-compose.yml`
- **Verification:** `docker compose ps` shows api as `(healthy)` after rebuild
- **Committed in:** 722b524 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - bug)
**Impact on plan:** Both auto-fixes required for correct operation. No scope creep.

## Issues Encountered

- The existing docker-compose.yml (from Plan 01) didn't have the redis healthcheck or migrate service; the new version adds proper service ordering so api waits for db+redis to be healthy and migration to complete before starting.
- npm audit warnings in frontend Docker build are pre-existing dev dependency warnings (not production security issues); noted but out of scope for this plan.

## User Setup Required

None — stack runs self-contained via docker compose. Admin setup uses environment-variable-driven seed script.

## Checkpoint Pending

Task 2 is a `checkpoint:human-verify` requiring human verification of the complete Phase 1 foundation end-to-end. See `.planning/phases/01-foundation/01-04-PLAN.md` Task 2 for verification steps.

## Next Phase Readiness

- Full Phase 1 foundation stack is running and verified via automated smoke tests
- Human verification of browser-based login flow is the only remaining step before Phase 1 is marked complete
- Phase 2 can begin in parallel — auth API is live, frontend shell is working, CI is configured

---
*Phase: 01-foundation*
*Completed: 2026-02-20 (Task 1); awaiting Task 2 human verification*

## Self-Check: PASSED

- FOUND: backend/Dockerfile
- FOUND: frontend/Dockerfile
- FOUND: frontend/nginx.conf
- FOUND: docker-compose.yml
- FOUND: docker-compose.prod.yml
- FOUND: .env.example
- FOUND: .github/workflows/test.yml
- FOUND: backend/tests/__init__.py
- FOUND: backend/tests/conftest.py
- FOUND: README.md
- FOUND: Task 1 commit 722b524 in git log
- API healthy: {"status":"ok","version":"1.0.0"} confirmed
- DB readiness: {"status":"ready","database":"ok"} confirmed
- Swagger UI: HTTP 200 at http://localhost:8000/api/docs confirmed
- Frontend: HTTP 200 at http://localhost:3000 confirmed
- Auth flow: admin login returned JWT access token; /auth/me returned user profile confirmed
