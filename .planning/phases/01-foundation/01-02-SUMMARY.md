---
phase: 01-foundation
plan: "02"
subsystem: auth
tags: [jwt, pyjwt, pwdlib, argon2, fastapi, sqlalchemy, asyncpg, oauth2, httponly-cookie, sha256]

# Dependency graph
requires:
  - phase: 01-foundation/01-01
    provides: User/UserSession ORM models, AsyncSessionLocal, get_db() stub, CredentialsException, FastAPI app skeleton, docker-compose DB
provides:
  - JWT access token issuance via create_access_token (PyJWT, HS256, 1-hour expiry)
  - JWT refresh token issuance via create_refresh_token (PyJWT, HS256, 7-day expiry, HttpOnly cookie)
  - SHA-256 token hashing via hash_token() for DB storage in user_sessions.token_hash
  - Argon2 password hashing via pwdlib[argon2]
  - get_current_user FastAPI dependency enforcing Bearer JWT on protected routes
  - POST /api/v1/auth/login — OAuth2PasswordRequestForm login, sets refresh_token HttpOnly cookie
  - POST /api/v1/auth/refresh — rotates access token via refresh cookie, validates user_sessions
  - POST /api/v1/auth/logout — revokes UserSession (revoked=True), clears cookie
  - GET /api/v1/auth/me — returns UserProfile (requires Bearer token)
  - OpenAPI Swagger UI at /api/docs listing all 6 endpoints with OAuth2 lock icons
affects: [03-frontend, 04-deployment, all-subsequent-phases]

# Tech tracking
tech-stack:
  added: []  # PyJWT and pwdlib already in requirements.txt from Plan 01
  patterns:
    - "OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login') in dependencies.py for FastAPI OpenAPI security schema generation"
    - "HttpOnly refresh token cookie scoped to path='/api/v1/auth' (not /) — limits exposure"
    - "SHA-256 hash of refresh token stored in user_sessions.token_hash — never store raw token in DB"
    - "cookie secure=True only in production (APP_ENV == 'production') — allows local HTTP dev"
    - "type claim in JWT payload ('access' vs 'refresh') enforced in get_current_user and refresh endpoint"

key-files:
  created:
    - backend/app/core/security.py
    - backend/app/schemas/user.py
    - backend/app/api/v1/auth.py
  modified:
    - backend/app/core/dependencies.py
    - backend/app/api/v1/router.py

key-decisions:
  - "Cookie path scoped to /api/v1/auth — reduces CSRF attack surface compared to path=/"
  - "Type claim in JWT ('access'/'refresh') enforced at decode time — prevents refresh token being used as access token and vice versa"
  - "oauth2_scheme tokenUrl points to /api/v1/auth/login — FastAPI auto-generates OAuth2 lock icons on protected endpoints in Swagger UI"
  - "timedelta import at module level in auth.py — avoided __import__ hack from initial plan draft"

patterns-established:
  - "Protected endpoint pattern: async def endpoint(current_user: User = Depends(get_current_user)) — FastAPI auto-enforces 401 on missing/invalid token"
  - "Session revocation pattern: UserSession.revoked=True + revoked_at timestamp in DB — instant revocation without JWT blocklist"
  - "Login response pattern: return access token in JSON body, set refresh token in HttpOnly cookie separately"

requirements-completed: [AUTH-01, AUTH-02, AUTH-03, API-02, API-03]

# Metrics
duration: 2min
completed: 2026-02-20
---

# Phase 1 Plan 02: Auth Endpoints Summary

**JWT authentication API with PyJWT + pwdlib[argon2]: login/refresh/logout/me endpoints, HttpOnly refresh cookie rotation, DB session revocation, and FastAPI OAuth2 lock icons on all protected routes**

## Performance

- **Duration:** 2 minutes
- **Started:** 2026-02-20T17:54:18Z
- **Completed:** 2026-02-20T17:56:40Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Security module (security.py) with PyJWT token issuance, pwdlib Argon2 password hashing, and SHA-256 token hashing — verified with round-trip test
- get_current_user dependency rejects tokens where type != "access", revoked sessions, and inactive users — wired into FastAPI OAuth2 security schema
- Four auth endpoints end-to-end verified against live Docker DB: login returns access token + HttpOnly cookie, refresh rotates access token, logout sets revoked=True in user_sessions, /me returns UserProfile
- OpenAPI Swagger UI at /api/docs shows all 6 endpoints (/auth/login, /auth/refresh, /auth/logout, /auth/me, /health, /health/ready) with OAuth2 lock icons on protected routes

## Task Commits

Each task was committed atomically:

1. **Task 1: Security module (JWT + password hashing) and auth dependencies** - `257b042` (feat)
2. **Task 2: Auth endpoints (login, refresh, logout, /auth/me)** - `eca7bf4` (feat)

**Plan metadata:** *(this commit)*

## Files Created/Modified

- `backend/app/core/security.py` - JWT encode/decode (PyJWT), pwdlib Argon2 password hashing, SHA-256 token hash
- `backend/app/core/dependencies.py` - get_db() + get_current_user() with OAuth2PasswordBearer and type-claim validation
- `backend/app/schemas/user.py` - LoginRequest, TokenResponse, UserProfile Pydantic models
- `backend/app/api/v1/auth.py` - POST /auth/login, POST /auth/refresh, POST /auth/logout, GET /auth/me
- `backend/app/api/v1/router.py` - Added include_router(auth.router) alongside health

## Decisions Made

- **Cookie scoped to path=/api/v1/auth:** Reduces CSRF attack surface. The refresh token cookie is only sent on auth endpoint requests, not every API call.
- **Type claim enforcement:** JWT payload includes "type": "access" or "type": "refresh". get_current_user rejects refresh tokens; the refresh endpoint rejects access tokens. Prevents token misuse.
- **oauth2_scheme tokenUrl=/api/v1/auth/login:** FastAPI reads this to auto-generate OAuth2 lock icons in Swagger UI on any endpoint using get_current_user. Satisfies API-03.
- **timedelta import at module level:** The initial plan draft used `__import__('datetime').timedelta` as an inline workaround. Replaced with proper `from datetime import datetime, timedelta, timezone` at the top of auth.py.

## Deviations from Plan

None - plan executed exactly as written. The timedelta import fix was flagged in the plan itself and applied as specified.

## Issues Encountered

None. The admin user was already seeded from Plan 01 execution, so verification was immediate.

## User Setup Required

None - auth endpoints use the existing docker-compose DB. No external services required.

## Next Phase Readiness

- Plan 03 (frontend) can begin: /api/v1/auth/login, /api/v1/auth/refresh, /api/v1/auth/logout, /api/v1/auth/me are all live
- Frontend must send `Authorization: Bearer <access_token>` header on protected API calls
- Frontend must NOT access the refresh_token cookie (it's HttpOnly — JS cannot read it)
- Refresh flow: frontend calls POST /api/v1/auth/refresh with credentials: 'include' — browser handles the HttpOnly cookie automatically

---
*Phase: 01-foundation*
*Completed: 2026-02-20*

## Self-Check: PASSED

- All 5 key files verified present on disk
- Task commits verified: 257b042 (Task 1), eca7bf4 (Task 2)
- No python-jose or passlib imports found in backend/
- security.py uses `import jwt` (PyJWT) confirmed
- security.py uses `from pwdlib import PasswordHash` confirmed
- type claim ("access"/"refresh") in create_access_token and create_refresh_token confirmed
- get_current_user rejects type != "access" confirmed
- OpenAPI spec shows all 4 auth endpoints confirmed via /openapi.json
- Session revoked=True verified in DB after logout
