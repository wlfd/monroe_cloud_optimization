# Testing Results Report -- CloudCost

Course: CS 701 -- Special Projects in Computer Science
Project: Cloud Infrastructure Cost Optimization Platform
Date: 2026-03-27

---

## 1. Executive Summary

| Metric | Backend | Frontend | Total |
|---|---|---|---|
| Test files | 10 | 13 | 23 |
| Test cases | 170 | 116 | 286 |
| Passed | 170 | 116 | 286 |
| Failed | 0 | 0 | 0 |
| Skipped | 0 | 1 | 1 |
| Pass rate | 100% | 99.1% | 99.7% |

All tests passing. One frontend test skipped (Radix Select portal behavior -- jsdom limitation, covered by manual testing).

---

## 2. Backend Test Results

**Framework:** pytest + pytest-asyncio
**Mock strategy:** AsyncMock for database sessions and Redis; MagicMock for external API clients (Azure, Anthropic)
**Fixture helpers:** `make_scalars_result()` and `make_scalar_result()` in `conftest.py` for mocking SQLAlchemy query results

### 2.1 Test File Summary

| Test File | Cases | Status | Description |
|---|---|---|---|
| `test_api_routes.py` | 21 | All pass | Integration tests for all API endpoints (auth, ingestion, cost, anomalies, recommendations, attribution, budgets, notifications, settings) |
| `test_security.py` | 20 | All pass | JWT creation and verification, password hashing (Argon2), brute-force lockout (5 attempts, 15-min lock), refresh token validation |
| `test_anomaly_service.py` | 21 | All pass | 30-day rolling baseline detection, severity classification (critical/high/medium), idempotent upsert, auto-resolve, status lifecycle |
| `test_ingestion_service.py` | 21 | All pass | Azure API mocking, billing record upsert, stale run recovery, 24-month backfill, delta window calculation, alert creation |
| `test_cost_service.py` | 14 | All pass | Cost aggregation queries (summary, breakdown, timeline, top resources), month-over-month delta, end-of-month projection |
| `test_recommendation_service.py` | 16 | All pass | LLM pipeline, Redis cache hits/misses, daily call counter, Anthropic tool output parsing, Azure OpenAI fallback |
| `test_attribution_service.py` | 19 | All pass | Tag-based cost allocation, rule priority ordering, CRUD operations, tenant profile management, manual attribution run |
| `test_budget_service.py` | 21 | All pass | Budget threshold checks, alert event creation, period spend calculation, soft-delete, scope filtering |
| `test_notification_service.py` | 17 | All pass | Email sending (SMTP), webhook delivery (HMAC signing), retry logic (3 attempts), notification routing, delivery history |
| **Total** | **170** | **All pass** | |

### 2.2 Areas Covered

- **Authentication and Authorization:** Login flow, JWT lifecycle, role-based access control, session management, brute-force protection
- **Data Ingestion:** Azure Cost Management API integration, record upsert with conflict handling, incremental fetch windows, backfill
- **Anomaly Detection:** Statistical baseline computation, deviation thresholds, severity classification, idempotent detection
- **AI Recommendations:** LLM prompt construction, structured output parsing, cache management, rate limiting, provider fallback
- **Cost Aggregation:** MTD/prior-month summaries, breakdowns by dimension, top resource ranking, CSV export
- **Multi-Tenant Attribution:** Tag matching, cost allocation algorithms, rule priority and reordering
- **Budget Management:** Threshold evaluation, period-aware spend calculation, alert event deduplication
- **Notifications:** Email and webhook delivery, HMAC signature generation, retry scheduling, delivery tracking

---

## 3. Frontend Test Results

**Framework:** Vitest 2.1.9 + React Testing Library
**Mock strategy:** MSW (Mock Service Worker) for API mocking
**Test utilities:** Custom `render()` wrapper from `test-utils.tsx` (wraps QueryClientProvider + BrowserRouter)

### 3.1 Test File Summary

| Test File | Cases | Status | Description |
|---|---|---|---|
| `pages/LoginPage.test.tsx` | 15 | All pass | Form rendering, credential submission, error display, loading states, token storage |
| `pages/DashboardPage.test.tsx` | 23 | All pass | Cost summary cards, trend chart, breakdown table, top resources, MoM delta display |
| `pages/AnomaliesPage.test.tsx` | 19 | 19 pass, 1 skip | Anomaly list, severity filtering, status updates, acknowledge action, summary cards |
| `pages/RecommendationsPage.test.tsx` | 6 | All pass | Recommendation list, category filtering, savings display, generate trigger |
| `pages/AttributionPage.test.tsx` | 8 | All pass | Attribution rules CRUD, tenant list, summary cards, manual run trigger |
| `pages/IngestionPage.test.tsx` | 7 | All pass | Run history table, manual trigger, status display, alert indicators |
| `pages/SettingsPage.test.tsx` | 5 | All pass | User management table, create user form, role assignment |
| `pages/NotFoundPage.test.tsx` | 3 | All pass | 404 rendering, dashboard link |
| `hooks/useAuth.test.tsx` | 7 | All pass | Session restore, login flow, credential format, logout, error handling |
| `services/api.test.tsx` | 8 | All pass | Axios configuration, JWT injection interceptor, 401 refresh/retry interceptor |
| `services/anomaly.test.tsx` | 7 | All pass | Anomaly list query, filters, error states, summary endpoint |
| `services/cost.test.tsx` | 4 | All pass | Spend summary, trend, breakdown, top resources hooks |
| `services/recommendation.test.tsx` | 4 | All pass | Recommendation list, summary, override handlers |
| **Total** | **116** | **116 pass, 1 skip** | |

### 3.2 Areas Covered

- **Page Components:** All 8 route-level pages tested (Login, Dashboard, Anomalies, Recommendations, Attribution, Ingestion, Settings, NotFound)
- **API Service Layer:** Axios instance configuration, auth interceptors, token refresh retry logic
- **Data Hooks:** TanStack Query hooks for cost, anomaly, and recommendation services
- **Auth Context:** Session persistence, login/logout flows, credential encoding
- **User Interactions:** Form submissions, button clicks, filter selections, loading/error state transitions

---

## 4. Test Execution Output

### 4.1 Frontend (Vitest)

```
 RUN  v2.1.9 /Users/wlfd/Developer/monroe_cloud_optimization/frontend

 Test Files  13 passed (13)
      Tests  116 passed | 1 skipped (117)
   Duration  1.78s (transform 545ms, setup 2.33s, collect 3.39s, tests 4.05s)
```

### 4.2 Backend (pytest)

Backend tests run via Docker (`make test-backend`) against mocked database sessions. 170 test cases across 10 files, all passing.

---

## 5. CI Pipeline Integration

Tests are automated in `.github/workflows/test.yml` on every push and pull request to `main`:

**Backend CI steps:**
1. PostgreSQL 15 service container spun up
2. Python 3.12 dependencies installed (cached)
3. `ruff check` -- lint
4. `ruff format --check` -- format verification
5. `alembic upgrade head` -- schema validation
6. `pytest tests/ -v --tb=short` -- unit tests

**Frontend CI steps:**
1. Node.js 24 dependencies installed (cached)
2. `tsc --noEmit` -- TypeScript type checking
3. `npm run build` -- production build verification
4. `npm run lint` -- ESLint
5. `npm run format:check` -- Prettier format verification
6. `npx vitest run` -- unit tests

---

## 6. Test Infrastructure

### 6.1 Backend Mock Patterns

- **Database:** `AsyncMock` wrapping SQLAlchemy `AsyncSession` with custom `make_scalars_result()` and `make_scalar_result()` helpers that simulate query execution chains
- **Redis:** `AsyncMock` for cache get/set/incr operations with controlled return values
- **Azure API:** `MagicMock` for `AzureClient` with configurable response data
- **Anthropic API:** `AsyncMock` for `AsyncAnthropic` client with structured tool-use response simulation
- **SMTP:** `MagicMock` for `aiosmtplib.SMTP` connection and send operations
- **HTTP (webhooks):** `AsyncMock` for `httpx.AsyncClient` post operations

### 6.2 Frontend Mock Patterns

- **MSW (Mock Service Worker):** Intercepts all API calls at the network level with predefined handlers in `test/mocks/handlers.ts`
- **Custom render:** `test-utils.tsx` wraps every component test with `QueryClientProvider` (fresh client per test) and `BrowserRouter`
- **jsdom polyfills:** `setup.ts` mocks `ResizeObserver`, `Element.setPointerCapture`, `Element.releasePointerCapture`, and `Element.hasPointerCapture` for Recharts and Radix UI compatibility

---

## 7. Known Limitations

| Limitation | Impact | Mitigation |
|---|---|---|
| Backend tests use mocked DB, not real PostgreSQL | Cannot catch SQL-specific bugs | Schema validated via `alembic upgrade head` in CI |
| No end-to-end tests | Critical user flows not tested automatically | Manual testing performed; E2E planned for future |
| 1 skipped frontend test (Radix Select portal) | Minor -- portal rendering in jsdom | Covered by manual browser testing |
| No coverage thresholds enforced | Could regress silently | Coverage reports available via `make test-backend-coverage` and `make test-frontend-coverage` |
