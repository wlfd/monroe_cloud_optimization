# Product Requirements Document
# Cloud Infrastructure Cost Optimization Platform

**Product:** CloudCost — Cloud Infrastructure Cost Optimization Platform
**Company:** Fileread (Seed-Stage Legal Tech Startup, $2.5M ARR)
**Author:** Tsun Shan Ho
**Date:** February 2026
**Version:** 2.0 (MVP Scope — Azure-Only, Monolith-First, Python/FastAPI)

---

## Revision History

| Version | Date | Change Summary |
|---------|------|----------------|
| 1.0 | Feb 2026 | Initial draft — tech stack TBD, microservices pattern |
| 2.0 | Feb 2026 | Finalized tech stack (Python/FastAPI/PostgreSQL/React), switched to modular monolith architecture, expanded DB schema to 23 entities, added background job schedule, deployment strategy |

---

## 1. Executive Summary

Fileread is a seed-stage legal tech startup preparing for Series A funding. Its cloud infrastructure runs on Microsoft Azure and currently lacks visibility into spending, cost attribution by customer, or predictive insight into future costs. Internal analysis has identified over $300,000 in potential annual savings through better resource optimization.

CloudCost is an internal platform that sits between Fileread's Azure infrastructure and its engineering/finance teams. It provides real-time cost visibility, LLM-powered optimization recommendations, and per-customer cost attribution for ~30 tenants — enabling the finance and DevOps teams to understand, manage, and reduce cloud spend without automated risk.

**MVP targets:** Azure-only, 10–11 week build window (January–April 2026), solo developer part-time.

**Architecture decision:** Modular monolith (not microservices). Given the solo developer and 10-week constraint, a well-structured monolith with clear internal module boundaries ships faster, is easier to debug, and can be decomposed later if needed. See Section 6.1.

---

## 2. Problem Statement

As Fileread scales toward Series A, cloud infrastructure costs are rising without commensurate visibility or control:

- **No real-time visibility** — The team doesn't know current Azure spend until billing cycles close. Anomalies go undetected for days.
- **No per-customer cost tracking** — Fileread cannot calculate true unit economics (infrastructure cost per customer), which is critical for investor diligence and pricing decisions.
- **No cost forecasting** — There is no ability to predict month-end spend or identify optimization opportunities proactively.
- **Manual optimization** — Right-sizing, idle resource identification, and budget management are done ad hoc and inconsistently.
- **Compliance gaps** — No immutable audit trail of platform actions for SOC 2 and HIPAA requirements.

The result: wasted spend, unknown unit economics, and a weak cost story for Series A investors.

---

## 3. Goals and Non-Goals

### 3.1 Goals (MVP — Spring 2026)

1. Provide real-time visibility into Azure cloud spending with drill-down by service, resource group, and tag
2. Alert the team when spending approaches or exceeds budget thresholds
3. Detect cost anomalies automatically and surface them with estimated dollar impact
4. Generate LLM-powered optimization recommendations (read-only, human-approved)
5. Track per-customer infrastructure costs using Azure resource tags across ~30 tenants
6. Expose a REST API and webhook/email notifications for alerts
7. Maintain a basic audit log of all platform actions

### 3.2 Non-Goals (Deferred to Future Phases)

- Automated execution of optimization actions (no automated resource termination or resizing)
- AWS or GCP integration
- Full compliance/governance module (SOC 2, HIPAA, GDPR policy engine)
- Third-party integrations (Terraform, Kubernetes, DataDog, Slack, PagerDuty)
- Custom ML model training
- Financial invoicing or billing system integration
- On-premises infrastructure support

---

## 4. Users and Stakeholders

### 4.1 User Personas

| Role | Primary Needs |
|------|---------------|
| **Platform Administrator** | Connect Azure accounts, configure tags, manage users, set alert rules |
| **Finance Team** | View total spend, set budgets, track per-customer costs, export reports |
| **DevOps Engineer** | Investigate cost anomalies, review optimization recommendations, drill down to resource level |
| **C-Level Executive** | High-level spend summary, month-over-month trends, unit economics |

### 4.2 Key Stakeholders

| Stakeholder | Role |
|-------------|------|
| Fileread Engineering Team | Primary end users |
| Fileread Management | Project sponsor, budget approval |
| Dr. Samson Ogola | Academic advisor (Monroe University CS 701) |

---

## 5. Core Features

### Module 1: Azure Data Ingestion Pipeline

**What it does:** Connects to the Azure Cost Management API, ingests billing and usage data, normalizes it, and stores it for querying.

**Requirements:**
- Authenticate with Azure using service principal credentials (stored encrypted, AES-256)
- Pull billing data from Azure Cost Management API on a configurable schedule (minimum every 4 hours, default 4 hours)
- Normalize billing data into a unified internal schema
- Support ingestion of historical data (up to 24 months)
- Handle API rate limits and transient failures with retry logic and exponential backoff (max 3 retries, backoff: 5s, 30s, 120s)
- Log all ingestion runs with status, row counts, and duration in the audit trail
- Support incremental ingestion (only pull data since last successful run)

**Acceptance Criteria:**
- Billing data is visible in the dashboard within 4 hours of an Azure charge
- Historical data from Fileread's Azure account loads successfully on initial setup
- Failed ingestion runs trigger an alert to administrators
- Ingestion is idempotent (re-running does not create duplicates)

---

### Module 2: Real-Time Cost Monitoring Dashboard

**What it does:** Provides a web-based UI showing current Azure cloud spending with drill-down capabilities.

**Requirements:**
- Display total month-to-date spend with a projected month-end figure
- Show daily spend trend chart (last 30/60/90 days, selectable)
- Break down costs by: Azure service type, resource group, subscription, region, and custom tags
- Show top 10 most expensive services/resources
- Compare current period spend to previous period (MoM, YoY)
- Support date range selection for historical analysis
- Export cost data to CSV
- Dashboard queries return in under 2 seconds
- Data auto-refreshes every 15 minutes (no manual refresh required)

**Key Screens:**
- **Overview Dashboard** — KPI cards (total spend, projected month-end, savings achieved, active anomalies), daily trend chart, spend breakdown table
- **Cost Breakdown** — Drill-down by service → resource group → individual resource
- **Service Detail** — Resource-level cost view with usage metrics

**Acceptance Criteria:**
- User can view total current-month Azure spend on the dashboard
- User can drill down from service-level to individual resource costs
- Data refreshes automatically every 15 minutes
- User can export a cost breakdown to CSV

---

### Module 3: Budget Management and Alerting

**What it does:** Allows users to set spending budgets and receive threshold-based alerts before costs spiral.

**Requirements:**
- Create budgets scoped to: subscription, resource group, service type, or tag
- Set multiple alert thresholds per budget (configurable; e.g., 50%, 75%, 90%, 100%)
- Deliver alerts via email and webhook (configurable per budget)
- Display budget vs. actual spend with a visual progress indicator
- Support monthly and annual budget periods
- Show alert history with timestamp, threshold triggered, and amount at alert
- Budget check runs every 4 hours aligned with ingestion schedule

**Acceptance Criteria:**
- User can create a budget with custom thresholds
- Alert email is delivered within 15 minutes of a threshold being crossed
- Budget vs. actual visualization correctly reflects current spend
- Alert history is accessible and filterable

---

### Module 4: Cost Anomaly Detection

**What it does:** Automatically detects unusual spending patterns and surfaces them with context.

**Algorithm:** Statistical deviation from a 30-day rolling baseline per service/resource group. An anomaly is flagged when current daily spend exceeds the rolling average by more than the configured deviation threshold.

**Requirements:**
- Calculate a 30-day rolling baseline mean and standard deviation per service/resource group
- Flag spending increases greater than a configurable deviation threshold (default: 20% above rolling mean)
- Detect new services not previously used (net-new spend detected as first occurrence)
- Assign severity based on estimated dollar impact:
  - **Critical:** projected monthly impact > $1,000 or deviation > 50%
  - **High:** projected monthly impact > $500 or deviation > 30%
  - **Medium:** projected monthly impact > $100 or deviation > 20%
- Display active anomalies with: service affected, estimated dollar impact, time of detection, affected resources
- Allow users to mark anomalies as "Expected" (suppresses future alerts for that pattern for 30 days) or "Dismissed"
- Configurable sensitivity: deviation threshold, minimum dollar impact to generate an alert
- Anomaly detection runs after each ingestion cycle (every 4 hours)

**Acceptance Criteria:**
- An anomaly is detected and surfaced within 4 hours of the triggering spend
- User can view estimated dollar impact for each anomaly
- User can mark an anomaly as Expected or Dismissed
- False positive rate is below 10% after one week of baseline data

---

### Module 5: AI-Powered Optimization Recommendations

**What it does:** Uses an LLM to analyze cost and usage data and generate actionable, plain-language optimization recommendations.

**Design constraint:** Recommendations only — no automated execution. All suggestions require explicit human review and approval before any action is taken.

**LLM Strategy:**
- Primary: Azure OpenAI (gpt-4o-mini for routine batch analysis, gpt-4o for complex multi-service analysis)
- Fallback: Anthropic Claude (claude-haiku-4-5 for routine, claude-sonnet-4-5 for complex)
- Routing rule: if estimated_monthly_savings > $500, use more capable model; otherwise use cheaper model
- Response caching: Cache LLM outputs in Redis with 24-hour TTL, keyed by hash of input data context
- Daily usage limit: configurable max API calls per day (default: 100 calls/day)

**Requirements:**
- Analyze cost trends and usage patterns from ingested billing data
- Generate recommendations in natural language explaining the issue, the suggested action, and the estimated monthly savings
- Categorize recommendations: right-sizing, idle resources, reserved instance opportunities, storage tier optimization
- Assign a confidence score (0–100) and estimated savings to each recommendation
- Display confidence indicators and savings estimates in the UI
- Allow users to accept (mark for action), dismiss, or defer each recommendation
- Implement LLM response caching to reduce API costs for repeated queries
- Set configurable usage limits on LLM API calls per day
- Recommendation generation runs once daily (scheduled overnight)

**Acceptance Criteria:**
- At least 3 actionable optimization recommendations are generated from Fileread's real Azure billing data
- Each recommendation includes: plain-language explanation, estimated monthly savings, confidence level
- User can accept or dismiss a recommendation
- LLM API costs are bounded by configurable daily limits

---

### Module 6: Multi-Tenant Cost Attribution

**What it does:** Maps Azure infrastructure costs to Fileread's ~30 customers using Azure resource tags, enabling per-customer unit economics.

**Requirements:**
- Read Azure resource tags to map resources to tenant IDs
- Support configurable tag key names (e.g., `tenant_id`, `customer`, `client`)
- Batch process attribution on a daily schedule (midnight UTC)
- Handle shared/untagged resources via proportional allocation rules (configurable: by-tenant-count, by-usage, or manual percentage splits)
- Calculate per-tenant monthly infrastructure cost
- Display per-tenant cost trends over time
- Generate monthly per-tenant cost reports exportable to CSV
- Allow administrators to define and update allocation rules without data loss (changes apply to future runs only; historical allocations are preserved)

**Acceptance Criteria:**
- Administrator can configure tag-to-tenant mappings
- Monthly infrastructure cost is calculated for each of Fileread's ~30 customers
- Shared resource costs are allocated according to configured rules
- Per-tenant cost report is exportable to CSV

---

### Module 7: REST API and Notifications

**What it does:** Exposes cost data and recommendations programmatically, and delivers notifications via webhooks and email.

**Requirements:**
- REST API endpoints for: current cost data, budget status, anomalies, recommendations, tenant attribution
- API authentication via API keys (rotated every 90 days; rotation reminder sent 7 days before expiry)
- Webhook delivery for: budget threshold alerts, anomaly detection events, new recommendations
- Email notification delivery for all alert types
- API documentation (OpenAPI/Swagger spec auto-generated by FastAPI)
- Rate limiting: 100 requests/minute per API key
- All API responses return within 2 seconds
- Webhook retries: 3 attempts with exponential backoff on failure

**Acceptance Criteria:**
- API returns current cost data in JSON format
- Webhook fires within 15 minutes of a triggering event
- API documentation is complete and accurate (auto-generated at /docs)
- API authentication rejects unauthenticated requests

---

### Module 8: Audit Logging

**What it does:** Maintains a tamper-resistant log of all platform actions for accountability and future compliance needs.

**Requirements:**
- Log all configuration changes (budget creation/modification, tag mapping changes, user settings)
- Log all user actions (logins, report exports, recommendation acceptances/dismissals)
- Log all system events (ingestion runs, anomaly detections, alert deliveries)
- Each log entry includes: timestamp (UTC), actor (user ID or "system"), action type, entity type, entity ID, before/after state (JSON diff)
- Audit log is append-only (no deletion or modification permitted at the application layer)
- Audit log is queryable by date range, actor, and action type
- Export audit log to JSON or CSV

**Acceptance Criteria:**
- Every user action generates a corresponding audit log entry
- Audit log entries are immutable
- Administrator can filter and export the audit log

---

## 6. Technical Requirements

### 6.1 Architecture

**Decision: Modular Monolith (not microservices)**

Rationale: Given the solo developer and 10-week build window, a microservices architecture introduces significant operational overhead (service discovery, inter-service auth, distributed tracing, multiple deployment units). A well-structured monolith with clear internal module boundaries achieves the same logical separation while being dramatically faster to build, test, and debug. Services can be extracted to independent deployments in a future phase if needed.

The application is organized as a single deployable unit with distinct internal modules:

```
cloudcost/
├── backend/                    # Python/FastAPI application
│   ├── app/
│   │   ├── modules/
│   │   │   ├── ingestion/      # Azure API integration
│   │   │   ├── monitoring/     # Cost analytics and queries
│   │   │   ├── budgets/        # Budget management and alerts
│   │   │   ├── anomaly/        # Anomaly detection engine
│   │   │   ├── recommendations/ # LLM recommendation engine
│   │   │   ├── attribution/    # Multi-tenant attribution
│   │   │   ├── api_keys/       # External API key management
│   │   │   ├── notifications/  # Email and webhook delivery
│   │   │   ├── audit/          # Audit logging
│   │   │   └── users/          # Auth and RBAC
│   │   ├── api/v1/             # FastAPI routers
│   │   ├── tasks/              # Celery background tasks
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── core/               # Config, DB, auth utilities
│   │   └── main.py             # FastAPI app entry point
│   ├── migrations/             # Alembic migrations
│   └── tests/
├── frontend/                   # React/TypeScript application
│   └── src/
├── docker-compose.yml          # Local development
└── docker-compose.prod.yml     # Production
```

### 6.2 Tech Stack (Finalized)

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Cloud Provider | Microsoft Azure (MVP) | Fileread's existing infrastructure |
| Billing API | Azure Cost Management REST API v2 | Official Azure billing data source |
| AI/LLM Primary | Azure OpenAI (gpt-4o-mini / gpt-4o) | Low latency, same Azure tenant |
| AI/LLM Fallback | Anthropic Claude (claude-haiku-4-5 / claude-sonnet-4-5) | Fallback if Azure OpenAI unavailable |
| Backend Framework | Python 3.11 + FastAPI | Async, auto-generates OpenAPI docs, great for data-heavy apps |
| Background Jobs | Celery 5 + Redis | Reliable task queue for scheduled ingestion and processing |
| Cache | Redis | LLM response caching, Celery broker |
| Database | PostgreSQL 15 | Normalized relational data, strong JSON support for audit logs |
| ORM | SQLAlchemy 2.0 + Alembic | Industry standard, migrations included |
| Frontend | React 18 + TypeScript | Type safety, large ecosystem |
| UI Components | shadcn/ui + Tailwind CSS | Fast to build, accessible components |
| Charts | Recharts | Composable React charts |
| API | REST with OpenAPI (auto-generated by FastAPI at /docs) | |
| Auth | JWT (access tokens, 1h expiry) + refresh tokens (7d) | Stateless, secure |
| Azure Auth | Azure Service Principal (MSAL Python SDK) | Official Azure SDK authentication |
| Encryption at rest | AES-256 for stored credentials (using Python cryptography library) | |
| Encryption in transit | TLS 1.3 | |
| Secrets Management | Azure Key Vault | Prod secrets storage |
| Containerization | Docker + Docker Compose | Consistent environments |
| Deployment | Azure Container Apps | Serverless containers on Azure |
| CI/CD | GitHub Actions | Automated test and deploy pipeline |

### 6.3 Database Schema (23 Entities)

#### Authentication & Users
| Entity | Purpose |
|--------|---------|
| `user` | Platform users — id, email, password_hash, role (admin/devops/finance/viewer), is_active, created_at, last_login |
| `user_session` | Active JWT refresh token sessions — id, user_id, token_hash, expires_at, ip_address, revoked |
| `api_key` | External REST API keys — id, key_hash, key_prefix (display), name, owner_user_id, expires_at, last_used_at, is_active |

#### Azure Account Management
| Entity | Purpose |
|--------|---------|
| `cloud_provider` | Azure provider configuration — id, name, provider_type ('azure'), created_by, created_at |
| `cloud_account` | Azure subscription configs — id, provider_id, subscription_id, tenant_id, client_id, encrypted_client_secret, display_name, is_active, last_sync_at |
| `ingestion_run` | Audit of data ingestion executions — id, account_id, started_at, completed_at, status (success/failed/running), rows_ingested, error_message |

#### Cost Data
| Entity | Purpose |
|--------|---------|
| `resource` | Azure resources with lifecycle — id, account_id, azure_resource_id, name, resource_type, resource_group, region, subscription_id, tags (JSONB), first_seen_at, last_seen_at |
| `billing_data` | Immutable billing records (append-only) — id, account_id, resource_id, service_name, resource_group, subscription_id, date, cost_usd, usage_quantity, usage_unit, tags (JSONB), billing_period |
| `billing_tag` | Flattened tag key-value pairs for indexed querying — id, billing_data_id, tag_key, tag_value |

#### Budget Management
| Entity | Purpose |
|--------|---------|
| `budget` | Budget configurations — id, name, account_id, scope_type (subscription/resource_group/service/tag), scope_value, amount_usd, period (monthly/annual), start_date, end_date, created_by |
| `budget_threshold` | Alert thresholds per budget — id, budget_id, threshold_percent (e.g., 75), notification_channel_id, last_triggered_at |
| `alert_event` | Fired alert instances — id, budget_id, threshold_id, triggered_at, spend_at_trigger, threshold_percent, delivery_status |

#### Notifications
| Entity | Purpose |
|--------|---------|
| `notification_channel` | Email or webhook endpoints — id, name, channel_type (email/webhook), config_json (address or URL + secret), owner_user_id, is_active |
| `notification_delivery` | Delivery attempt log — id, channel_id, event_type, event_id, attempt_number, attempted_at, status (delivered/failed), response_code, error_message |

#### Anomaly Detection
| Entity | Purpose |
|--------|---------|
| `anomaly` | Detected spending anomalies — id, account_id, service_name, resource_group, detected_at, baseline_daily_avg, actual_daily_spend, deviation_percent, severity (critical/high/medium), estimated_monthly_impact, status (active/expected/dismissed), resolved_by_user_id, resolved_at |
| `anomaly_resource` | Resources linked to a specific anomaly — id, anomaly_id, resource_id, cost_delta |

#### LLM Recommendations
| Entity | Purpose |
|--------|---------|
| `optimization_recommendation` | LLM-generated recommendations — id, account_id, category (right-sizing/idle/reserved/storage), title, description, recommended_action, estimated_monthly_savings, confidence_score (0-100), status (pending/accepted/dismissed/deferred), model_used, generated_at, actioned_by_user_id, actioned_at |
| `llm_cache` | Cached LLM responses to control costs — id, cache_key (SHA-256 of input), model, response_json, created_at, expires_at, hit_count |

#### Multi-Tenant Attribution
| Entity | Purpose |
|--------|---------|
| `tenant` | Fileread customer tenants — id, tenant_name, tenant_identifier, tag_key, tag_value, is_active, created_at |
| `allocation_rule` | Rules for shared/untagged resource cost splits — id, account_id, rule_name, method (by_tenant_count/by_usage/manual_percent), manual_splits_json, is_active, effective_from |
| `resource_tenant_mapping` | Tag-based resource-to-tenant assignments — id, resource_id, tenant_id, mapping_source (tag/rule), allocation_percent, effective_from, effective_to |
| `tenant_cost_allocation` | Computed monthly cost per tenant (output of daily attribution job) — id, tenant_id, account_id, billing_period (YYYY-MM), total_cost_usd, direct_cost_usd, allocated_shared_cost_usd, run_at |

#### Audit
| Entity | Purpose |
|--------|---------|
| `audit_log` | Immutable platform event log — id (auto-increment only), timestamp (UTC), actor_type (user/system), actor_id, action_type, entity_type, entity_id, before_state (JSONB), after_state (JSONB), ip_address, request_id |

**Total: 23 entities**

### 6.4 Background Job Schedule

All scheduled tasks run via Celery with a Redis broker. Beat scheduler handles cron-style scheduling.

| Job | Schedule | Description |
|-----|----------|-------------|
| `ingest_billing_data` | Every 4 hours | Pull latest billing data from Azure Cost Management API for all active accounts |
| `run_anomaly_detection` | Every 4 hours (30 min after ingestion) | Recalculate baselines and detect anomalies on fresh data |
| `check_budget_thresholds` | Every 4 hours (60 min after ingestion) | Evaluate all budgets against current spend; fire alerts if thresholds crossed |
| `run_tenant_attribution` | Daily at 02:00 UTC | Batch-process tag-based cost attribution for all tenants |
| `generate_recommendations` | Daily at 03:00 UTC | Send billing data summary to LLM and store new recommendations |
| `expire_llm_cache` | Daily at 04:00 UTC | Delete expired LLM cache entries from Redis |
| `api_key_rotation_reminder` | Daily at 09:00 UTC | Check for API keys expiring within 7 days and send email reminders |
| `retry_failed_webhooks` | Every 15 minutes | Retry webhook deliveries that failed (up to 3 attempts) |

### 6.5 Performance Requirements

- Dashboard page load: < 2 seconds
- API response time: < 2 seconds for all endpoints
- Cost data freshness: updated at least every 4 hours
- Batch attribution processing: completes within 2 hours of daily trigger
- Database indexes required on: `billing_data(account_id, date)`, `billing_data(service_name, billing_period)`, `billing_data(resource_group)`, `billing_tag(tag_key, tag_value)`, `audit_log(timestamp)`, `audit_log(actor_id)`, `anomaly(status, detected_at)`, `tenant_cost_allocation(tenant_id, billing_period)`

### 6.6 Security Requirements

- All Azure credentials stored encrypted at rest (AES-256, key stored in Azure Key Vault)
- All data in transit encrypted (TLS 1.3)
- Role-based access control (Admin, DevOps, Finance, Viewer)
- API token rotation every 90 days (with 7-day advance reminder)
- Session timeout: JWT access token expires in 1 hour; refresh token expires in 7 days
- Audit log is append-only (no UPDATE or DELETE permitted on audit_log table at DB level via row-level trigger or policy)
- Rate limiting: 100 requests/minute per API key; 5 failed login attempts triggers 15-minute account lockout
- Password requirements: minimum 12 characters, bcrypt hashing

### 6.7 Deployment Architecture

**Development (local):**
- `docker-compose.yml` runs: FastAPI app, Celery worker, Celery beat, Redis, PostgreSQL
- FastAPI hot-reload enabled
- React dev server with proxy to FastAPI

**Production (Azure):**
- FastAPI app → Azure Container App (auto-scales 1–3 instances)
- Celery worker → Azure Container App (dedicated worker, 1 instance)
- Celery beat → Azure Container App (1 instance, single scheduler)
- Redis → Azure Cache for Redis (Basic tier)
- PostgreSQL → Azure Database for PostgreSQL Flexible Server
- React frontend → Azure Static Web Apps (CDN-backed)
- Secrets → Azure Key Vault (referenced by Container Apps via managed identity)

**CI/CD (GitHub Actions):**
- On pull request: run tests (pytest), lint (ruff + mypy)
- On merge to main: build Docker images, push to Azure Container Registry, deploy to Azure Container Apps

---

## 7. User Stories (MVP Scope)

### Epic 1: Platform Setup

**US-001: Initial Platform Setup**
As a Platform Administrator, I want to connect Fileread's Azure account so the system can begin collecting billing data.
- Configure Azure service principal credentials
- Verify billing API access
- Store credentials encrypted
- Log setup in audit trail

**US-002: Azure Provider Configuration**
As a Platform Administrator, I want to configure which subscriptions and resource groups to monitor.

**US-003: User Access Management**
As a Platform Administrator, I want to create user accounts with role-based access so team members have appropriate visibility.
- Roles: Admin, DevOps, Finance, Viewer
- Email-based user creation
- Role assignment

### Epic 2: Cost Monitoring

**US-004: Real-Time Cost Dashboard**
As a Finance Team member, I want to view current Azure spending so I can monitor costs throughout the billing period.
- Total MTD spend with projected month-end
- Breakdown by service and resource group
- Daily trend chart

**US-005: Cost Breakdown by Service**
As a DevOps Engineer, I want to see which Azure services are driving costs so I can prioritize optimization efforts.
- Top 10 most expensive services
- Drill-down to resource level
- Export to CSV

**US-006: Budget Configuration**
As a Finance Team member, I want to set monthly budgets with alert thresholds so we can prevent cost overruns.
- Budgets at subscription, resource group, or tag level
- Configurable alert thresholds (50%, 75%, 90%, 100%)
- Email and webhook notifications

### Epic 3: Anomaly Detection

**US-007: Automated Anomaly Detection**
As a DevOps Engineer, I want to be alerted when spending patterns are unusual so I can investigate quickly.
- Statistical deviation from 30-day rolling baseline
- Severity levels with dollar impact estimates
- Configurable sensitivity thresholds

**US-008: Anomaly Investigation**
As a DevOps Engineer, I want to understand which resources caused an anomaly so I can take corrective action.
- Resource-level drill-down from anomaly
- Mark as Expected or Dismiss
- View affected resources

### Epic 4: AI Recommendations

**US-009: Cost Optimization Recommendations**
As a Platform Administrator, I want AI-generated recommendations for reducing costs so I can act without manual analysis.
- Natural language explanations
- Estimated monthly savings per recommendation
- Confidence scores
- Accept/Dismiss/Defer actions (no auto-execution)

**US-010: Recommendation History**
As a Finance Team member, I want to track which recommendations have been accepted and their realized savings.

### Epic 5: Multi-Tenant Attribution

**US-011: Tenant Resource Mapping**
As a Platform Administrator, I want to map Azure resources to Fileread's customers via tags so we can calculate per-customer costs.
- Configure tag key for tenant identification
- Define shared resource allocation rules
- Validate mapping coverage (report what % of spend is untagged)

**US-012: Per-Tenant Cost Views**
As a Finance Team member, I want to see monthly infrastructure cost per customer so we can understand unit economics.
- Monthly cost per tenant
- Cost trends over time per tenant
- Export per-tenant report to CSV

### Epic 6: API and Notifications

**US-013: REST API Access**
As a DevOps Engineer, I want programmatic access to cost data so we can integrate with internal tooling.
- Authenticated REST API
- Endpoints for costs, anomalies, recommendations, tenant attribution
- OpenAPI documentation (auto-generated at /api/docs)

**US-014: Webhook Notifications**
As a Platform Administrator, I want webhook delivery for alerts so we can route them to our internal systems.

### Epic 7: Audit and Reporting

**US-015: Audit Log**
As a Platform Administrator, I want a log of all platform actions so we have accountability and a compliance foundation.
- Append-only log of all changes
- Filterable by date, user, action type
- CSV export

---

## 8. Success Criteria

### Business Success Criteria
- Platform provides real-time visibility into Fileread's Azure spending (< 4-hour lag)
- Per-customer cost tracking is operational for all ~30 Fileread customers
- AI recommendations identify at least 3 actionable optimization opportunities from real billing data
- Platform is stable enough for production use at Fileread by April 2026

### Technical Success Criteria
- Azure Cost Management API integration functional end-to-end
- Dashboard loads within 2 seconds
- Anomaly detection false positive rate < 10%
- All platform actions logged in audit trail
- REST API documented and functional (Swagger UI available at /api/docs)
- Test coverage ≥ 70% on backend service layer

---

## 9. Out of Scope

| Feature | Reason |
|---------|--------|
| Automated execution of optimization actions | Too risky for production legal tech environment; one bad automation = outage |
| AWS / GCP integration | Fileread is Azure-only; multi-cloud triples integration work |
| Full compliance policy engine (SOC 2, HIPAA, GDPR) | High effort, not needed for MVP; design documentation from CS 700 preserved for future |
| Third-party tool integrations (Terraform, K8s, DataDog, Slack, PagerDuty) | Each is its own mini-project; REST API + webhooks covers core notification needs |
| Custom ML model training | Requires months of data and MLOps infrastructure; LLM API approach is faster and sufficient |
| Financial invoicing / billing system | Out of scope for an internal cost visibility tool |
| On-premises infrastructure | Azure-only for MVP |
| Kubernetes cost allocation | Deferred; requires separate metrics integration |

---

## 10. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Azure API changes during development | Low | Pin to stable API version (2023-04-01); monitor Azure changelog |
| LLM API costs exceed budget | Medium | Cache responses 24h in Redis; use smaller models for routine analysis; set daily usage limits (default 100 calls/day) |
| LLM recommendations are inaccurate | Medium | Human approval required for all recommendations; confidence scores; iterate on prompts |
| Insufficient Azure billing data for testing | Low | Use Fileread's real Azure exports; Azure provides sample datasets as fallback |
| Timeline slippage (solo developer, part-time) | Medium | Weekly scope check; priority order if cuts needed: anomaly detection > LLM recommendations > tenant attribution > API |
| Scope creep | Medium | This PRD establishes clear boundaries; additional features deferred to future phases |
| Redis cache failure | Low | LLM calls fall back to direct API; Celery tasks retry automatically |

---

## 11. Future Phases (Deferred)

The following capabilities have complete design documentation from CS 700 and are planned for future implementation:

- **Automated Resource Optimization Workflows** — Right-sizing, idle resource termination, scheduled start/stop for dev environments, spot instance management (with full approval + rollback workflows)
- **Compliance and Governance Module** — SOC 2, HIPAA, GDPR policy engine, compliance scoring, regulatory reporting
- **Integration Hub** — Terraform provider, Kubernetes cost allocation, DataDog correlation, CI/CD pipeline cost checks, Slack/Teams notifications
- **Multi-cloud expansion** — AWS Cost Explorer and GCP Billing integration
- **Advanced Analytics** — What-if scenario modeling, reserved instance optimizer, storage tier automation
- **Microservices decomposition** — Extract ingestion, attribution, and recommendation engines to independent services if scale demands it

---

## 12. Financial Context

| Metric | Value |
|--------|-------|
| Identified annual savings opportunity | $300,000+ |
| Expected platform ROI (3-year) | 180% |
| Payback period | ~6 months post-deployment |
| Fileread current ARR | $2.5M |
| Target tenant count | ~30 customers |

---

*Document version 2.0 — February 2026*
*Reflects finalized MVP scope: Python/FastAPI backend, modular monolith architecture, 23-entity PostgreSQL schema, Celery background jobs*
*(CS 701, Spring 2026 implementation)*
