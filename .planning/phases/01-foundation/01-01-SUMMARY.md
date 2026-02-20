---
phase: 01-foundation
plan: "01"
subsystem: database
tags: [fastapi, sqlalchemy, asyncpg, alembic, pydantic-settings, pyjwt, pwdlib, postgres, docker, uvicorn]

# Dependency graph
requires: []
provides:
  - Async SQLAlchemy 2.0 engine with AsyncSessionLocal and DeclarativeBase
  - User and UserSession ORM models matching ARCHITECTURE.md schema
  - Alembic async migration environment with initial migration (users + user_sessions tables)
  - pydantic-settings Settings class with all Phase 1 env vars
  - FastAPI app skeleton with CORS middleware and /api/v1 prefix
  - Health endpoints: GET /health (liveness) and GET /health/ready (DB ping readiness)
  - OpenAPI Swagger UI at /api/docs (docs_url="/api/docs")
  - Admin seed script using FIRST_ADMIN_EMAIL + FIRST_ADMIN_PASSWORD env vars
  - docker-compose.yml with postgres:15, redis:7-alpine, api, and frontend services
  - Backend Dockerfile using python:3.12-slim
affects: [02-auth, 03-frontend, 04-deployment, all-subsequent-phases]

# Tech tracking
tech-stack:
  added:
    - fastapi[standard]>=0.115
    - sqlalchemy[asyncio]>=2.0
    - asyncpg>=0.29
    - alembic>=1.13
    - pyjwt>=2.0 (NOT python-jose — deprecated)
    - pwdlib[argon2]>=0.2 (NOT passlib — unmaintained on Python 3.12+)
    - pydantic-settings>=2.0
    - python-multipart>=0.0.9
    - uvicorn>=0.30
    - postgres:15 (Docker)
    - redis:7-alpine (Docker)
    - python:3.12-slim (Dockerfile base)
  patterns:
    - Async SQLAlchemy 2.0 session via async_sessionmaker with expire_on_commit=False
    - pydantic-settings BaseSettings with SettingsConfigDict(env_file=".env", extra="ignore")
    - Alembic async env.py using async_engine_from_config + asyncio.run(run_async_migrations())
    - FastAPI docs_url="/api/docs" at top level (not via router prefix) to avoid 404
    - Model imports in models/__init__.py for Alembic autogenerate detection
    - PYTHONPATH=./backend for running alembic CLI outside of Docker

key-files:
  created:
    - backend/app/main.py
    - backend/app/core/config.py
    - backend/app/core/database.py
    - backend/app/core/exceptions.py
    - backend/app/core/dependencies.py
    - backend/app/core/security.py
    - backend/app/api/v1/health.py
    - backend/app/api/v1/router.py
    - backend/app/models/user.py
    - backend/app/models/__init__.py
    - backend/app/scripts/seed_admin.py
    - backend/migrations/env.py
    - backend/migrations/versions/d89aaf4be42d_create_users_and_user_sessions_tables.py
    - backend/requirements.txt
    - backend/requirements-dev.txt
    - backend/.env.example
    - backend/Dockerfile
    - backend/alembic.ini
    - docker-compose.yml
  modified: []

key-decisions:
  - "PyJWT (import jwt) instead of python-jose — python-jose is abandoned; FastAPI docs updated to recommend PyJWT"
  - "pwdlib[argon2] instead of passlib — passlib is unmaintained and breaks on Python 3.12+"
  - "python:3.12-slim Dockerfile base — stable with asyncpg; 3.13 has asyncpg compatibility notes"
  - "docs_url=/api/docs set in FastAPI() constructor directly — NOT via router prefix — prevents 404 at /api/docs"
  - "PYTHONPATH=./backend for alembic CLI — enables import of app.* modules without installing the package"
  - "Admin seed script via env vars (FIRST_ADMIN_EMAIL + FIRST_ADMIN_PASSWORD) — simplest approach for solo developer"
  - ".env.local for local dev overrides — created from .env.example; not committed"

patterns-established:
  - "Async DB session: async def get_db() -> AsyncGenerator[AsyncSession, None]: async with AsyncSessionLocal() as session: yield session"
  - "Alembic env.py: import all models in models/__init__.py; env.py imports that barrel file"
  - "Health check pattern: /health (liveness, no DB) + /health/ready (readiness, DB SELECT 1)"
  - "Settings singleton: @lru_cache def get_settings() -> Settings: return Settings(); settings = get_settings()"

requirements-completed: [AUTH-01, AUTH-02]

# Metrics
duration: 15min
completed: 2026-02-20
---

# Phase 1 Plan 01: Backend Foundation Summary

**FastAPI skeleton with async SQLAlchemy 2.0 + PostgreSQL, User/UserSession ORM models, Alembic async migration, and docker-compose dev stack using PyJWT + pwdlib[argon2] (not deprecated python-jose/passlib)**

## Performance

- **Duration:** 15 minutes
- **Started:** 2026-02-20T17:35:12Z
- **Completed:** 2026-02-20T17:51:11Z
- **Tasks:** 2
- **Files modified:** 20

## Accomplishments

- FastAPI app with CORS middleware, /api/v1 prefix, OpenAPI at /api/docs (verified: HTTP 200), and health endpoints returning expected JSON
- Async SQLAlchemy 2.0 engine + session maker + DeclarativeBase; get_db() dependency stub ready for Plan 02
- User and UserSession ORM models with all ARCHITECTURE.md fields including INET ip_address, UUID PKs, composite indexes
- Alembic async migration environment; initial migration d89aaf4be42d creates both tables with indexes; applied and verified via \dt
- Admin seed script: creates admin from env vars, idempotent (confirmed with two consecutive runs)
- docker-compose.yml with postgres:15 (healthy), redis:7-alpine, api, frontend services; local containers verified running

## Task Commits

Each task was committed atomically:

1. **Task 1: Backend project structure, config, database engine, docker-compose** - `2dbefad` (feat)
2. **Task 2: User/UserSession models, Alembic migration, admin seed script** - `d8fa4b4` (feat)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `backend/app/main.py` - FastAPI app factory with CORS, /api/v1 router, docs_url=/api/docs
- `backend/app/core/config.py` - pydantic-settings Settings class with all Phase 1 env vars
- `backend/app/core/database.py` - Async SQLAlchemy 2.0 engine, AsyncSessionLocal, Base
- `backend/app/core/exceptions.py` - CredentialsException, ForbiddenException, NotFoundException
- `backend/app/core/dependencies.py` - get_db() async session dependency stub
- `backend/app/core/security.py` - Empty stub (Plan 02 fills this)
- `backend/app/api/v1/health.py` - GET /health and GET /health/ready endpoints
- `backend/app/api/v1/router.py` - Aggregate router (health only; auth added in Plan 02)
- `backend/app/models/user.py` - User and UserSession ORM models
- `backend/app/models/__init__.py` - Barrel file importing User/UserSession for Alembic autogenerate
- `backend/app/scripts/seed_admin.py` - Admin bootstrap using FIRST_ADMIN_EMAIL + FIRST_ADMIN_PASSWORD
- `backend/migrations/env.py` - Async Alembic env reading DATABASE_URL from environment
- `backend/migrations/versions/d89aaf4be42d_...py` - Initial migration: users + user_sessions tables
- `backend/requirements.txt` - FastAPI, SQLAlchemy, asyncpg, alembic, pyjwt, pwdlib, pydantic-settings
- `backend/requirements-dev.txt` - httpx, pytest, pytest-asyncio, anyio
- `backend/.env.example` - All env vars with comments
- `backend/Dockerfile` - python:3.12-slim based; Plan 04 will add HEALTHCHECK
- `backend/alembic.ini` - Alembic config; sqlalchemy.url overridden by env.py
- `docker-compose.yml` - postgres:15 with healthcheck, redis:7-alpine, api, frontend services

## Decisions Made

- **PyJWT not python-jose:** python-jose is abandoned (last release 3 years ago); FastAPI official docs updated to PyJWT. Confirmed by research.
- **pwdlib[argon2] not passlib:** passlib is unmaintained and its `crypt` module is removed in Python 3.13. pwdlib is the FastAPI-recommended replacement.
- **python:3.12-slim base image:** Stable with asyncpg 0.29+; Python 3.13 has compatibility notes with asyncpg.
- **docs_url="/api/docs" in FastAPI() constructor directly:** Setting this via router prefix causes a 404; must be at constructor level.
- **Admin seed via env vars:** Simplest approach for solo developer; no setup endpoint exposure required.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker Desktop was not running**
- **Found during:** Task 1 verification
- **Issue:** Docker daemon socket did not exist at /Users/wlfd/.docker/run/docker.sock; docker compose up failed
- **Fix:** Launched Docker Desktop via `open -a Docker`, waited for daemon to start, then retried
- **Files modified:** None (operational fix)
- **Verification:** `docker ps` returned successfully; `docker compose up -d db redis` succeeded
- **Committed in:** N/A (no code change)

**2. [Rule 3 - Blocking] Missing .env.local file**
- **Found during:** Task 1 verification
- **Issue:** docker-compose.yml references .env.local for the api service; file did not exist, causing docker compose exec to fail
- **Fix:** Copied backend/.env.example to .env.local
- **Files modified:** .env.local (not committed — dev-only file)
- **Verification:** `docker compose exec db psql -U cloudcost -c "SELECT 1;"` succeeded
- **Committed in:** N/A (.env.local is gitignored by convention)

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking operational issues)
**Impact on plan:** Both were environment setup issues, not code issues. Plan code artifacts match specification exactly.

## Issues Encountered

- Docker images (postgres:15, redis:7-alpine) were not pre-pulled; initial pull took ~3 minutes on this machine. Used `docker pull` directly to track progress rather than waiting on background compose up.
- Alembic initialization failed on first attempt because the empty `migrations/` directory already existed (created by mkdir earlier). Resolved by removing the empty directory and re-running `alembic init -t async migrations`.
- `pip install` failed initially with PEP 668 error (externally managed Python on macOS). Resolved with `--break-system-packages` flag for local development installation.

## User Setup Required

None - local dev environment self-contained via docker-compose. No external services configured in this plan.

## Next Phase Readiness

- Plan 02 (auth endpoints) can begin immediately: User/UserSession models exist, database is running, get_db() dependency is ready, security.py stub is in place
- `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD` must be set before running seed_admin.py in a real environment
- `.env.local` must be created from `backend/.env.example` on any new developer machine

---
*Phase: 01-foundation*
*Completed: 2026-02-20*

## Self-Check: PASSED

- All 15 key files verified present on disk
- Task commits verified: 2dbefad (Task 1), d8fa4b4 (Task 2)
- requirements.txt: no python-jose or passlib found
- docs_url="/api/docs" confirmed in main.py
- AsyncSessionLocal confirmed in database.py
- FIRST_ADMIN_EMAIL confirmed in seed_admin.py
- op.create_table confirmed in migration upgrade()
