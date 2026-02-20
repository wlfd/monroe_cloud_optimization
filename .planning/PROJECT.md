# CloudCost

## What This Is

CloudCost is an internal cloud cost optimization platform built for Fileread, a seed-stage legal tech startup running on Microsoft Azure. It gives Fileread's engineering and finance teams real-time visibility into Azure spending, automatic anomaly detection, per-customer cost attribution across ~30 tenants, and LLM-powered recommendations — surfacing the $300K+ annual savings opportunity identified in internal analysis.

## Core Value

AI-powered optimization recommendations that identify savings Fileread actually implements — not just dashboard numbers, but actionable intelligence that moves spending down.

## Requirements

### Validated

(None yet — ship to validate)

### Active

#### Data Ingestion
- [ ] System ingests Azure billing data every 4 hours via Cost Management API
- [ ] Ingestion is incremental (only pulls since last successful run)
- [ ] System handles API rate limits with exponential backoff (3 retries: 5s, 30s, 120s)
- [ ] Historical data backfill covers up to 24 months on first setup
- [ ] Ingestion runs are idempotent (re-run does not create duplicates)
- [ ] Failed ingestion triggers an admin alert

#### Cost Monitoring Dashboard
- [ ] User can view total month-to-date Azure spend with projected month-end
- [ ] User can see daily spend trend (30/60/90 day views, selectable)
- [ ] User can break down costs by: service, resource group, subscription, region, tag
- [ ] User can view top 10 most expensive services/resources
- [ ] User can compare current period spend to previous period (MoM)
- [ ] User can export cost data to CSV
- [ ] Dashboard data auto-refreshes every 15 minutes
- [ ] Dashboard queries respond in under 2 seconds

#### Cost Anomaly Detection
- [ ] System detects spending anomalies using 30-day rolling baseline per service/resource group
- [ ] Anomaly severity assigned by estimated dollar impact (Critical >$1K, High >$500, Medium >$100)
- [ ] System detects first appearance of new Azure services as anomaly type
- [ ] User can view affected resources and estimated dollar impact per anomaly
- [ ] User can mark an anomaly as Expected or Dismissed
- [ ] Anomaly detection runs after every ingestion cycle

#### AI Optimization Recommendations
- [ ] System generates LLM-powered optimization recommendations daily
- [ ] Each recommendation includes: plain-language explanation, estimated monthly savings, confidence score (0–100)
- [ ] Recommendations categorized by type: right-sizing, idle resources, reserved instances, storage tier
- [ ] User can accept, dismiss, or defer each recommendation (no auto-execution)
- [ ] LLM responses cached 24h (Redis) to control API costs
- [ ] Configurable daily LLM call limit (default: 100/day)
- [ ] Primary LLM: Azure OpenAI (gpt-4o-mini / gpt-4o); fallback: Anthropic Claude

#### Multi-Tenant Cost Attribution
- [ ] System maps Azure resources to tenants via `tenant_id` tag on a daily schedule
- [ ] System supports shared/untagged resource allocation rules (by-tenant-count, by-usage, manual %)
- [ ] User can view monthly infrastructure cost per tenant
- [ ] User can export per-tenant cost report to CSV
- [ ] Admin can define and update allocation rules without data loss

#### REST API & Notifications
- [ ] REST API exposes cost data, anomalies, recommendations, and tenant attribution
- [ ] API requires authentication (JWT sessions + API keys)
- [ ] Webhook delivery for budget alerts, anomaly events, new recommendations
- [ ] Email notification delivery for all alert types
- [ ] API documentation auto-generated at /api/docs (FastAPI + OpenAPI)
- [ ] API keys rotate every 90 days (7-day advance reminder)

#### Audit Logging
- [ ] All user actions and system events written to append-only audit log
- [ ] Each entry includes: timestamp (UTC), actor, action type, entity, before/after state
- [ ] Audit log is immutable (no UPDATE or DELETE at DB layer)
- [ ] Admin can query audit log by date range, actor, and action type

### Out of Scope

- Budget Management (set budgets, threshold alerts) — time trade-off; anomaly detection covers emergency spend visibility; deferred to v2
- Automated resource execution (resize, terminate) — read-only for MVP; automation deferred until recommendations build trust
- AWS and GCP integration — Fileread is Azure-only; multi-cloud triples integration work
- Full compliance policy engine (SOC 2, HIPAA, GDPR) — designed in CS 700; deferred to future phase
- Third-party integrations (Slack, PagerDuty, Terraform, Kubernetes, DataDog) — REST API + webhooks covers core notification needs for MVP
- Custom ML model training — LLM API approach is faster and sufficient
- Financial invoicing / billing system integration — out of scope for internal cost visibility tool
- On-premises infrastructure support — Azure-only for MVP

## Context

**Company:** Fileread, seed-stage legal tech startup, ~$2.5M ARR, ~30 customers (tenants)

**Infrastructure:** Azure-only. All customer workloads run on Azure; resources are consistently tagged with `tenant_id`, making direct tag-based attribution viable without heavy allocation rule work.

**Financial driver:** Internal analysis identified $300K+ in potential annual savings. CloudCost is the vehicle to find and capture those savings. Platform ROI projected at 180% over 3 years, ~6 month payback.

**Series A context:** Per-customer unit economics (infrastructure cost per tenant) is a material input to investor diligence. Attribution module is the enabler.

**Academic context:** CS 701 course project at Monroe University under Dr. Samson Ogola. April 2026 submission deadline is non-negotiable.

**Design artifacts:** Full architecture document at `ARCHITECTURE.md` (database schema, API catalog, background job specs, Azure ingestion design, LLM integration design, multi-tenant attribution flow, auth/RBAC matrix, deployment topology). PRD v2.0 at `PRD_v2.md`.

**Prior design:** CS 700 produced compliance/governance design documentation preserved for future phases.

## Constraints

- **Tech Stack**: Python 3.11 + FastAPI + SQLAlchemy 2.0 + Alembic | Celery 5 + Redis | PostgreSQL 15 | React 18 + TypeScript + shadcn/ui + Recharts — finalized, not open for change
- **Architecture**: Modular monolith (not microservices) — single deployable unit with clear internal module boundaries; can decompose later
- **Timeline**: April 2026 hard deadline (CS 701); solo developer, part-time
- **Azure-only**: No AWS or GCP in MVP scope
- **Read-only**: No automated resource execution; all recommendations require human approval
- **Deployment**: Azure Container Apps (API + worker + beat) + Azure Static Web Apps (frontend) + Azure DB for PostgreSQL + Azure Cache for Redis
- **Security**: Azure credentials encrypted AES-256 in DB; Key Vault in production; JWT auth; RBAC (admin, devops, finance, viewer); API key 90-day rotation; audit log immutable at DB level

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Modular monolith over microservices | Solo developer + 10-week window; monolith ships faster, easier to debug; can decompose later | — Pending |
| Azure OpenAI primary, Anthropic fallback | Same Azure tenant = lower latency; Anthropic fallback prevents single-provider lock | — Pending |
| Budget management deferred to v2 | Time trade-off; attribution provides more unique value (unit economics for Series A); anomaly detection covers emergency spend alerts | — Pending |
| Read-only recommendations for MVP | Too risky to auto-execute in a production legal tech environment; trust must be established first | — Pending |
| Tag-based attribution (no heavy allocation rules needed) | Fileread consistently tags resources with `tenant_id` today; direct mapping works | — Pending |
| LLM response caching in Redis (24h TTL) | Controls API costs; bounded by configurable daily call limit (default 100/day) | — Pending |

---
*Last updated: 2026-02-20 after initialization*
