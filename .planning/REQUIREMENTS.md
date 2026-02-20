# Requirements: CloudCost

**Defined:** 2026-02-20
**Core Value:** AI-powered optimization recommendations that identify savings Fileread actually implements

## v1 Requirements

Requirements for initial release. Each maps to a roadmap phase.

### Authentication

- [ ] **AUTH-01**: User can log in with email and password and receive a JWT access token
- [ ] **AUTH-02**: User session persists via 7-day refresh token across browser restarts
- [ ] **AUTH-03**: User can log out and invalidate their current session

### Ingestion

- [ ] **INGEST-01**: System ingests Azure billing data from Cost Management API on a 4-hour schedule
- [ ] **INGEST-02**: System performs 24-month historical data backfill on first account setup
- [ ] **INGEST-03**: System retries failed API calls with exponential backoff (3 retries: 5s, 30s, 120s)
- [ ] **INGEST-04**: Ingestion is idempotent — re-runs do not create duplicate billing records
- [ ] **INGEST-05**: Failed ingestion runs generate an admin alert notification
- [ ] **INGEST-06**: All ingestion runs are logged with status, row count, and duration

### Cost Monitoring

- [ ] **COST-01**: User can view total month-to-date Azure spend with projected month-end figure
- [ ] **COST-02**: User can compare current period spend to previous period (MoM)
- [ ] **COST-03**: User can view daily spend trend chart with selectable 30, 60, and 90-day views
- [ ] **COST-04**: User can break down costs by service, resource group, region, and tag
- [ ] **COST-05**: User can view top 10 most expensive resources for any selected period
- [ ] **COST-06**: User can export cost breakdown data to CSV

### Anomaly Detection

- [ ] **ANOMALY-01**: System detects spending anomalies via 30-day rolling baseline per (service, resource group) pair
- [ ] **ANOMALY-02**: System assigns severity (Critical/High/Medium) based on estimated monthly dollar impact
- [ ] **ANOMALY-03**: System calculates estimated monthly dollar impact for each detected anomaly
- [ ] **ANOMALY-04**: User can view a list of anomalies with severity, affected service, and dollar impact

### AI Recommendations

- [ ] **AI-01**: System generates LLM-powered optimization recommendations on a daily schedule (Azure OpenAI primary, Anthropic Claude fallback)
- [ ] **AI-02**: Each recommendation includes: category (right-sizing/idle/reserved/storage), plain-language explanation, estimated monthly savings, and confidence score (0–100)
- [ ] **AI-03**: LLM responses are cached in Redis with 24-hour TTL to minimize API costs
- [ ] **AI-04**: System enforces a configurable daily LLM call limit (default: 100 calls/day)

### Multi-Tenant Attribution

- [ ] **ATTR-01**: System maps Azure resources to tenants via `tenant_id` resource tag on a daily schedule
- [ ] **ATTR-02**: Admin can define shared/untagged resource allocation rules (by-tenant-count, by-usage, or manual percentage splits)
- [ ] **ATTR-03**: User can view monthly infrastructure cost per tenant
- [ ] **ATTR-04**: User can export per-tenant cost report to CSV

### REST API

- [ ] **API-01**: Authenticated REST API exposes endpoints for costs, anomalies, recommendations, and tenant attribution
- [ ] **API-02**: API requires JWT bearer token authentication
- [ ] **API-03**: OpenAPI documentation auto-generated and accessible at /api/docs

### Audit Logging

- [ ] **AUDIT-01**: All user actions and system events are written to an append-only audit log
- [ ] **AUDIT-02**: Each audit entry includes: timestamp (UTC), actor (user ID or system), action type, entity type, entity ID, before/after state (JSON)
- [ ] **AUDIT-03**: Audit log is immutable — no UPDATE or DELETE permitted at the database layer

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Budget Management

- **BUDG-01**: Admin can create a budget scoped to subscription, resource group, service, or tag
- **BUDG-02**: Admin can set multiple alert thresholds per budget (configurable percentages)
- **BUDG-03**: User can view budget vs. actual spend with visual progress indicator
- **BUDG-04**: Alert fires when spend crosses a configured threshold

### Recommendations Workflow

- **AI-05**: User can mark a recommendation as Accepted, Dismissed, or Deferred
- **AI-06**: User can view accepted recommendations and track realized savings

### Anomaly Workflow

- **ANOMALY-05**: User can mark an anomaly as Expected (suppresses for 30 days) or Dismissed
- **ANOMALY-06**: System detects new Azure services (first-appearance anomaly type)

### Notifications

- **NOTIF-01**: System delivers webhook notifications for budget, anomaly, and recommendation events
- **NOTIF-02**: System delivers email notifications for all alert types with 3-retry backoff

### Access Control & Security

- **AUTH-04**: Role-based access control (admin, devops, finance, viewer) restricts UI and API access by role
- **AUTH-05**: Admin can create and manage user accounts and assign roles
- **AUTH-06**: API keys with 90-day rotation and 7-day advance reminder
- **AUTH-07**: Account lockout after 5 failed login attempts (15-minute lockout)

### Audit UI

- **AUDIT-04**: Admin can query audit log by date range, actor, and action type via the UI
- **AUDIT-05**: Admin can export filtered audit log to CSV or JSON

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automated resource execution (resize, terminate) | Too risky for production legal tech environment; read-only for MVP; deferred until recommendations build trust |
| AWS and GCP integration | Fileread is Azure-only; multi-cloud triples integration scope |
| Full compliance policy engine (SOC 2, HIPAA, GDPR) | High effort; designed in CS 700; preserved for future phase |
| Slack, PagerDuty, Terraform, Kubernetes integrations | Each is its own mini-project; REST API + webhooks (v2) covers core needs |
| Custom ML model training | LLM API approach faster and sufficient; MLOps infra not available |
| Financial invoicing / billing system integration | Out of scope for internal cost visibility tool |
| On-premises infrastructure support | Azure-only for MVP |
| Kubernetes cost allocation | Requires separate metrics integration |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01 | TBD | Pending |
| AUTH-02 | TBD | Pending |
| AUTH-03 | TBD | Pending |
| INGEST-01 | TBD | Pending |
| INGEST-02 | TBD | Pending |
| INGEST-03 | TBD | Pending |
| INGEST-04 | TBD | Pending |
| INGEST-05 | TBD | Pending |
| INGEST-06 | TBD | Pending |
| COST-01 | TBD | Pending |
| COST-02 | TBD | Pending |
| COST-03 | TBD | Pending |
| COST-04 | TBD | Pending |
| COST-05 | TBD | Pending |
| COST-06 | TBD | Pending |
| ANOMALY-01 | TBD | Pending |
| ANOMALY-02 | TBD | Pending |
| ANOMALY-03 | TBD | Pending |
| ANOMALY-04 | TBD | Pending |
| AI-01 | TBD | Pending |
| AI-02 | TBD | Pending |
| AI-03 | TBD | Pending |
| AI-04 | TBD | Pending |
| ATTR-01 | TBD | Pending |
| ATTR-02 | TBD | Pending |
| ATTR-03 | TBD | Pending |
| ATTR-04 | TBD | Pending |
| API-01 | TBD | Pending |
| API-02 | TBD | Pending |
| API-03 | TBD | Pending |
| AUDIT-01 | TBD | Pending |
| AUDIT-02 | TBD | Pending |
| AUDIT-03 | TBD | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 33 ⚠️

---
*Requirements defined: 2026-02-20*
*Last updated: 2026-02-20 after initial definition*
