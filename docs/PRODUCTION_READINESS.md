# Production Readiness Review — CloudCost

_Generated: 2026-03-27_

## Status Legend

- [ ] Not started
- [x] Complete

---

## 1. CI/CD Gaps (High Priority)

- [ ] Frontend tests don't run in CI (`.github/workflows/test.yml` only type-checks and builds)
- [ ] Frontend linting not in CI (`eslint` and `prettier` checks skipped)
- [ ] No coverage reporting (no `--coverage` flag or threshold enforcement)
- [ ] No pre-commit hooks (no `.pre-commit-config.yaml`)
- [ ] No deployment pipeline (no CD config for staging/production)

## 2. Testing Gaps (High Priority)

- [ ] No E2E tests (no Playwright/Cypress for critical user flows)
- [ ] Backend: `cost.py` service has zero dedicated tests
- [ ] Backend: `recommendation.py` service has zero dedicated tests
- [ ] Frontend: `AttributionPage.tsx` untested
- [ ] Frontend: `RecommendationsPage.tsx` untested
- [ ] Frontend: `IngestionPage.tsx` untested
- [ ] Frontend: `SettingsPage.tsx` untested
- [ ] Frontend: `NotFoundPage.tsx` untested
- [ ] Frontend: `cost.ts` service untested
- [ ] Frontend: `attribution.ts` service untested
- [ ] Frontend: `ingestion.ts` service untested
- [ ] Frontend: `recommendation.ts` service untested
- [ ] Mocked-only DB tests (no tests against real PostgreSQL)
- [ ] No coverage thresholds configured

## 3. Python Static Type Checking (Medium Priority)

- [ ] No mypy or pyright configured despite extensive type hints
- [ ] Add mypy to CI pipeline

## 4. Inline Documentation (Medium Priority)

- [ ] Backend function docstrings sparse on CRUD/service methods
- [ ] Frontend components lack JSDoc
- [ ] Code references external decision docs (AUTH-01, AI-02, API-03) not in repo
- [ ] Add ADR (Architecture Decision Records) to `docs/adr/`

## 5. Dependency Pinning (Medium Priority)

- [ ] Backend `requirements.txt` uses `>=` — no lockfile for reproducible builds
- [ ] Adopt `pip-tools` or `poetry` for backend dependency locking
- [ ] Verify `package-lock.json` is committed for frontend

## 6. Scalability Concerns (Medium Priority)

- [ ] Single-process APScheduler — no distributed lock for multi-instance
- [ ] No pagination on cost breakdown / CSV export (memory risk)
- [ ] No API rate limiting beyond auth lockout
- [ ] No multi-tenancy row-level security

## 7. Observability (Medium Priority)

- [ ] No structured logging (stdlib logging, no JSON format)
- [ ] No APM / tracing (no OpenTelemetry, Sentry, etc.)
- [ ] No metrics endpoint (no Prometheus `/metrics`)

## 8. Missing Production Config

- [ ] CORS origins need production lockdown
- [ ] No runtime log level configuration
- [ ] No graceful shutdown drain for in-flight requests
- [ ] No database backup/restore strategy documented

## 9. Developer Experience

- [ ] Add CLAUDE.md for AI-assisted development
- [ ] Add standalone CONTRIBUTING.md (currently embedded in README)
- [ ] No Storybook component catalog
- [ ] No API changelog / versioning strategy beyond `/api/v1`
- [x] Auto-seed admin account on `docker compose up` (seed service)

---

## Recommended Priority Order

1. Fix CI: frontend test + lint steps, coverage thresholds
2. Add pre-commit hooks: ruff + eslint + type-check
3. Pin dependencies: pip-tools or poetry for backend lockfile
4. Add E2E tests: Playwright for login → dashboard → export
5. Add mypy: static type checking for Python
6. Fill test gaps: cost service, recommendation service, remaining frontend pages
7. Add structured logging + health metrics
8. Document ADRs: move AUTH-01/AI-02 references into docs/adr/
9. Add rate limiting: per-user request throttling
10. Pagination: server-side cursor pagination for cost queries
