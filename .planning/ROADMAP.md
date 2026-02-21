# Roadmap: CloudCost

## Overview

CloudCost delivers Azure cost visibility and AI-powered savings recommendations to Fileread's engineering and finance teams. The platform is built in seven sequential phases: a deployable foundation with auth, a reliable data ingestion pipeline, a cost monitoring dashboard, anomaly detection, AI optimization recommendations, per-tenant cost attribution, and a finalized REST API with immutable audit logging. Each phase produces a coherent, usable capability that unblocks the next.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - Deployable project skeleton with database, auth, and API infrastructure (completed 2026-02-20)
- [x] **Phase 2: Data Ingestion** - Azure billing pipeline with scheduling, backfill, and reliability guarantees (completed 2026-02-21)
- [x] **Phase 3: Cost Monitoring** - Dashboard with spend views, trend analysis, breakdowns, and CSV export (completed 2026-02-21)
- [x] **Phase 4: Anomaly Detection** - Rolling-baseline anomaly detection with severity and dollar impact (completed 2026-02-21)
- [x] **Phase 5: AI Recommendations** - Daily LLM-powered optimization recommendations with caching and rate limiting (completed 2026-02-21)
- [ ] **Phase 6: Multi-Tenant Attribution** - Tag-based tenant cost mapping with allocation rules and per-tenant reporting
- [ ] **Phase 7: REST API and Audit** - Full authenticated API surface and immutable append-only audit log

## Phase Details

### Phase 1: Foundation
**Goal**: Engineers can deploy a running application with a healthy database, working authentication, and documented API endpoints
**Depends on**: Nothing (first phase)
**Requirements**: AUTH-01, AUTH-02, AUTH-03, API-02, API-03
**Success Criteria** (what must be TRUE):
  1. User can log in with email and password and receive a JWT access token
  2. User session persists across browser restarts via a 7-day refresh token
  3. User can log out and their session is invalidated immediately
  4. OpenAPI documentation is accessible at /api/docs and reflects all current endpoints
  5. The application deploys successfully to Azure Container Apps with a healthy status check
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md — Backend scaffold, async DB layer, User/UserSession models, Alembic, admin seed script
- [x] 01-02-PLAN.md — JWT auth API: login, refresh, logout, /auth/me endpoints + get_current_user dependency
- [x] 01-03-PLAN.md — React app shell: Vite + shadcn/ui, sidebar nav, topbar, login page, dashboard placeholder
- [x] 01-04-PLAN.md — Containerization: production Dockerfiles, docker-compose, GitHub Actions CI, README

### Phase 2: Data Ingestion
**Goal**: Azure billing data flows into the database reliably on schedule, with backfill for historical analysis
**Depends on**: Phase 1
**Requirements**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-05, INGEST-06
**Success Criteria** (what must be TRUE):
  1. Billing data appears in the database automatically every 4 hours without manual intervention
  2. Re-running an ingestion job against the same date range produces no duplicate billing records
  3. A first-time account setup triggers a 24-month historical backfill that completes without errors
  4. When the Azure Cost Management API fails, the system retries with exponential backoff before alerting
  5. An admin-visible alert appears when an ingestion run fails after all retries are exhausted
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — BillingRecord/IngestionRun/IngestionAlert models, Alembic migration, Azure config settings
- [x] 02-02-PLAN.md — Azure client (retry, pagination, mock mode) + ingestion service (delta window, upsert, backfill, alerts)
- [x] 02-03-PLAN.md — APScheduler lifespan integration (4-hour job) + ingestion admin API (/run, /status, /runs, /alerts)
- [x] 02-04-PLAN.md — Admin ingestion UI (status indicator, Run Now button, alert banner, run history table) + human verify

### Phase 3: Cost Monitoring
**Goal**: Users can see total Azure spend, trends, breakdowns, and top-cost resources through a live dashboard
**Depends on**: Phase 2
**Requirements**: COST-01, COST-02, COST-03, COST-04, COST-05, COST-06
**Success Criteria** (what must be TRUE):
  1. User can view total month-to-date Azure spend alongside a projected month-end figure on the dashboard
  2. User can compare current period spend to the previous period (month-over-month) without leaving the dashboard
  3. User can switch between 30, 60, and 90-day daily spend trend views and see the chart update
  4. User can break down costs by service, resource group, region, or tag and see updated figures
  5. User can export a cost breakdown to a CSV file that opens correctly in a spreadsheet application
**Plans**: 5 plans

Plans:
- [ ] 03-01-PLAN.md — Schema migration (region, tag, resource_id, resource_name cols) + Azure client QueryGrouping update + _map_record
- [ ] 03-02-PLAN.md — Cost service layer (5 aggregate query functions) + 6 FastAPI endpoints + router registration
- [ ] 03-03-PLAN.md — shadcn chart/tabs install + cost hooks (cost.ts) + DashboardPage KPI cards + AreaChart with day-range toggle
- [ ] 03-04-PLAN.md — shadcn select/table install + breakdown dimension table + top-10 resources table + CSV export button
- [ ] 03-05-PLAN.md — Human verification checkpoint: all 6 COST requirements verified end-to-end in browser

### Phase 4: Anomaly Detection
**Goal**: The system automatically surfaces unusual spending spikes with severity ratings and dollar impact so users can investigate quickly
**Depends on**: Phase 2
**Requirements**: ANOMALY-01, ANOMALY-02, ANOMALY-03, ANOMALY-04
**Success Criteria** (what must be TRUE):
  1. After each ingestion cycle, the system evaluates spend against a 30-day rolling baseline and flags deviations
  2. Each anomaly displayed to the user shows a severity label (Critical, High, or Medium) and the estimated monthly dollar impact
  3. User can view a list of current anomalies filtered by the affected service and resource group
  4. A spend spike that crosses the Critical threshold ($1K+ estimated impact) appears in the anomaly list after the next ingestion run
**Plans**: 5 plans

Plans:
- [ ] 04-01-PLAN.md — Anomaly SQLAlchemy model (billing.py) + Alembic migration creating anomalies table
- [ ] 04-02-PLAN.md — Detection service (run_anomaly_detection, upsert, auto-resolve, CRUD) + post-ingestion hook + Pydantic schemas + FastAPI router (6 endpoints)
- [ ] 04-03-PLAN.md — Frontend anomaly.ts service hooks + shadcn Badge install + App.tsx /anomalies route wiring
- [ ] 04-04-PLAN.md — AnomaliesPage.tsx (card list, KPI row, filters, actions, export, detection config) + DashboardPage anomaly summary card (4th KPI)
- [ ] 04-05-PLAN.md — Human verification checkpoint: all 4 ANOMALY requirements verified end-to-end

### Phase 5: AI Recommendations
**Goal**: The system generates daily LLM-powered cost optimization recommendations that engineers and finance can act on
**Depends on**: Phase 3
**Requirements**: AI-01, AI-02, AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. New optimization recommendations appear in the UI each day without manual triggering
  2. Each recommendation shows its category, a plain-language explanation, estimated monthly savings, and a confidence score
  3. Repeated LLM calls for the same resource within 24 hours use cached responses rather than hitting the API again
  4. The system stops generating new LLM calls when the configurable daily limit is reached and resumes the following day
**Plans**: 4 plans

Plans:
- [ ] 05-01-PLAN.md — Recommendation model + Alembic migration + Redis client singleton + config fields
- [ ] 05-02-PLAN.md — LLM service (Anthropic primary, Azure fallback, Redis cache, daily counter) + FastAPI router + scheduler daily job
- [ ] 05-03-PLAN.md — Frontend service hooks + RecommendationsPage (card list, filters, summary, limit banner, empty state) + App.tsx route
- [ ] 05-04-PLAN.md — Human verification checkpoint: all 4 AI requirements verified end-to-end

### Phase 6: Multi-Tenant Attribution
**Goal**: Finance and engineering can see infrastructure cost broken down by customer tenant, enabling unit economics reporting for Series A diligence
**Depends on**: Phase 2
**Requirements**: ATTR-01, ATTR-02, ATTR-03, ATTR-04
**Success Criteria** (what must be TRUE):
  1. The system automatically maps Azure resources to tenants via `tenant_id` resource tags each day without manual steps
  2. Admin can define how shared or untagged resources are split across tenants (by tenant count, by usage, or by manual percentage)
  3. User can view the monthly infrastructure cost for each of Fileread's ~30 tenants on a single screen
  4. User can export a per-tenant cost report to CSV with each tenant's monthly cost as a separate row
**Plans**: TBD

### Phase 7: REST API and Audit
**Goal**: All platform data is accessible via an authenticated REST API and every user action is captured in an immutable audit trail
**Depends on**: Phase 6
**Requirements**: API-01, AUDIT-01, AUDIT-02, AUDIT-03
**Success Criteria** (what must be TRUE):
  1. API endpoints for costs, anomalies, recommendations, and tenant attribution all return correct data when called with a valid token
  2. Every user action (login, export, dismissal) and system event (ingestion run, anomaly detected) appears in the audit log within seconds
  3. Each audit entry contains timestamp (UTC), actor, action type, entity type, entity ID, and before/after state
  4. Attempting to UPDATE or DELETE an audit log record at the database layer is rejected by a constraint

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 4/4 | Complete    | 2026-02-20 |
| 2. Data Ingestion | 4/4 | Complete   | 2026-02-21 |
| 3. Cost Monitoring | 5/5 | Complete   | 2026-02-21 |
| 4. Anomaly Detection | 5/5 | Complete    | 2026-02-21 |
| 5. AI Recommendations | 4/4 | Complete    | 2026-02-21 |
| 6. Multi-Tenant Attribution | 0/TBD | Not started | - |
| 7. REST API and Audit | 0/TBD | Not started | - |

---
*Created: 2026-02-20*
*Requirements: 33 v1 requirements mapped across 7 phases*
