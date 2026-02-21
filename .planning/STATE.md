# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-20)

**Core value:** AI-powered optimization recommendations that identify savings Fileread actually implements
**Current focus:** Phase 6 - Multi-Tenant Attribution

## Current Position

**Phase:** 6 of 7 (Multi-Tenant Attribution)
**Current Plan:** 5
**Total Plans in Phase:** 5
**Status:** Ready to execute
**Last Activity:** 2026-02-21

**Progress:** [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 10 (Plans 01-01 through 04-01 fully complete)
- Average duration: 7 min
- Total execution time: 72 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 01-foundation | 5 | 47 min | 12 min |
| 02-data-ingestion | 3 | 13 min | 4 min |
| 03-cost-monitoring | 1 | 7 min | 7 min |

**Recent Trend:**
- Last 5 plans: 25 min, 5 min, 2 min, 8 min, 7 min
- Trend: Schema migrations with model + service updates average 7 min

*Updated after each plan completion*
| Phase 02 P03 | 8min | 2 tasks | 5 files |
| Phase 02-data-ingestion P04 | 15min | 2 tasks | 3 files |
| Phase 03-cost-monitoring P01 | 7min | 2 tasks | 4 files |
| Phase 03-cost-monitoring P02 | 3min | 2 tasks | 4 files |
| Phase 03-cost-monitoring P03 | 8 | 2 tasks | 4 files |
| Phase 03-cost-monitoring P04 | 2 | 2 tasks | 4 files |
| Phase 03-cost-monitoring P05 | 1 | 1 tasks | 0 files |
| Phase 04-anomaly-detection P01 | 7 | 1 tasks | 2 files |
| Phase 04-anomaly-detection P02 | 6 | 2 tasks | 5 files |
| Phase 04-anomaly-detection P03 | 1 | 1 tasks | 4 files |
| Phase 04-anomaly-detection P04 | 12 | 2 tasks | 2 files |
| Phase 04-anomaly-detection P05 | 525598min | 1 tasks | 4 files |
| Phase 04-anomaly-detection P05 | 15min | 1 tasks | 4 files |
| Phase 05-ai-recommendations P01 | 2 | 2 tasks | 6 files |
| Phase 05-ai-recommendations P02 | 3min | 2 tasks | 5 files |
| Phase 05-ai-recommendations P03 | 2min | 2 tasks | 3 files |
| Phase 05-ai-recommendations P04 | 0 | 1 tasks | 0 files |
| Phase 06-multi-tenant-attribution P01 | 1 | 2 tasks | 3 files |
| Phase 06-multi-tenant-attribution P02 | 3min | 2 tasks | 6 files |
| Phase 06-multi-tenant-attribution P03 | 8min | 2 tasks | 4 files |
| Phase 06-multi-tenant-attribution P04 | 1 | 1 tasks | 0 files |

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
- [Phase 03-cost-monitoring]: resource_id NOT added to unique constraint — keeps upsert semantics stable; resource columns are supplementary data for top-10 queries
- [Phase 03-cost-monitoring]: resource_name derived from last path segment of ResourceId at ingest time — no extra Azure QueryGrouping needed
- [Phase 03-cost-monitoring]: server_default='' added manually to autogenerated Alembic migration — autogenerate omits this for String columns; required for NOT NULL columns on existing tables
- [Phase 03-cost-monitoring]: tag column stores raw tenant_id tag value (empty string for untagged) — satisfies COST-04 and pre-seeds Phase 6 attribution
- [Phase 03-cost-monitoring]: MoM delta returns None when prior month has zero spend — avoids misleading percentage on first billing period
- [Phase 03-cost-monitoring]: DIMENSION_MAP in services/cost.py maps string keys to SQLAlchemy column refs — single source of truth for dimension validation
- [Phase 03-cost-monitoring]: Service layer returns raw result.all() rows; API layer maps to Pydantic models with explicit float() casts — decouples service from response format
- [Phase 03-cost-monitoring]: satisfies ChartConfig used for type narrowing on chartConfig — IDE autocomplete without widening the type
- [Phase 03-cost-monitoring]: connectNulls={true} on AreaChart Area component — prevents weekend/no-billing-day gaps in trend line (research pitfall #1)
- [Phase 03-cost-monitoring]: Tabs onValueChange drives days state -> useSpendTrend queryKey -> TanStack Query refetch — no polling needed
- [Phase 03-cost-monitoring]: Export button placed inline in Cost Breakdown card header (right of Select) — keeps action contextual to the data being viewed
- [Phase 03-cost-monitoring]: Export uses api singleton directly (not a hook) — one-time action, not server state; hooks are for queries not mutations
- [Phase 03-cost-monitoring]: Blob download pattern: responseType: blob + createObjectURL + link.click() + revokeObjectURL — established for any future CSV/PDF exports
- [Phase 03-cost-monitoring]: Phase 3 dashboard verified end-to-end by human — no defects found, no remediation required
- [Phase 04-anomaly-detection]: server_default='new' on status and server_default='false' on expected added to anomalies migration — allows direct SQL inserts without Python layer; follows Phase 3 precedent
- [Phase 04-anomaly-detection]: check_date uses MAX(usage_date) from billing_records rather than today-1 — robust to Azure data latency
- [Phase 04-anomaly-detection]: GET /filter-options returns combined {services, resource_groups} dict instead of two separate endpoints — one round-trip for UI dropdowns
- [Phase 04-anomaly-detection]: Detection accuracy: (total_non_dismissed - expected_count) / total_non_dismissed * 100; returns None when total_detected=0 (same null pattern as mom_delta_pct)
- [Phase 04-anomaly-detection]: AnomaliesPage.tsx stub created to resolve import before Plan 04 builds full component — avoids TS compilation errors while route is wired
- [Phase 04-anomaly-detection]: Dual useAnomalies() calls in AnomaliesPage: unfiltered for filter-option derivation, filtered for display — avoids separate API call from page layer
- [Phase 04-anomaly-detection]: Worst-severity label on Dashboard Active Anomalies card: shows highest-priority count in severity-appropriate color (Critical=red, High=orange, Medium=blue) when active_count > 0
- [Phase 04-anomaly-detection]: AnomalyCard defined inline in AnomaliesPage.tsx — keeps mutation hooks co-located with render, no prop-drilling
- [Phase 04-anomaly-detection]: Context-sensitive action buttons (show/hide by status) preferred over disabled buttons for anomaly card UX
- [Phase 04-anomaly-detection]: Toggle endpoint for anomaly expected flag: PATCH /{id}/expected accepts {expected: bool} — single endpoint for both mark and unmark
- [Phase 05-ai-recommendations]: utcnow() helper redefined locally in recommendation.py — keeps model files decoupled, consistent with billing.py pattern
- [Phase 05-ai-recommendations]: get_redis returns app.state.redis — Redis client initialized in main.py lifespan, injected via get_redis(request: Request) dependency
- [Phase 05-ai-recommendations]: generated_date as Date (not DateTime) in recommendations — daily-replace semantics; service queries WHERE generated_date = MAX(generated_date)
- [Phase 05-ai-recommendations]: migrations/env.py must import all model modules — alembic autogenerate only detects models loaded at import time (lesson from Task 2)
- [Phase 05-ai-recommendations]: require_admin imported from app.api.v1.ingestion (not app.api.v1.auth) — that is where require_admin is defined in this codebase
- [Phase 05-ai-recommendations]: Azure OpenAI fallback is graceful no-op when AZURE_OPENAI_ENDPOINT/KEY unset — logs warning and returns None, app works without it
- [Phase 05-ai-recommendations]: Daily limit counter incremented before LLM call (not after) — prevents races; cache hits bypass counter entirely
- [Phase 05-ai-recommendations]: No Apply/Dismiss/Accept buttons on recommendation cards — deferred to v2 per plan locked decision
- [Phase 05-ai-recommendations]: Phase 5 verified end-to-end by human — no defects found, no remediation required
- [Phase 06-multi-tenant-attribution]: Docker volume mount only covers backend/app — migrations/ dir must be docker cp'd into container for alembic autogenerate and upgrade commands
- [Phase 06-multi-tenant-attribution]: server_default='true' added on is_new Boolean in attribution migration — follows Phase 4 precedent for boolean server_defaults; new table so no backfill needed but keeps pattern consistent
- [Phase 06-multi-tenant-attribution]: _AttributionWithDisplayName wrapper class used for two-step join — TenantAttribution has no ORM relationship to TenantProfile; Python dict merge avoids JOIN complexity
- [Phase 06-multi-tenant-attribution]: apply_allocation_rule() is a pure function (not async) — takes cost + method + manual_pct + tenant_costs, returns dict; clean separation from DB layer
- [Phase 06-multi-tenant-attribution]: by_usage falls back to by_count when sum(tenant_costs) == 0 — prevents division-by-zero on first billing period
- [Phase 06-multi-tenant-attribution]: Non-fatal post-ingestion attribution hook with try/except — attribution failure does not fail the ingestion run record
- [Phase 06-multi-tenant-attribution]: onMouseDown(e.preventDefault()) on inline Save button prevents Input onBlur from cancelling edit before click handler fires — correct fix for save-before-blur React pattern
- [Phase 06-multi-tenant-attribution]: Phase 6 verified end-to-end by human — no defects found, no remediation required

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** 2026-02-21T22:00:53.074Z
**Stopped at:** Completed 06-multi-tenant-attribution-04-PLAN.md
**Resume file:** None
