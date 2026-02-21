# External Integrations

**Analysis Date:** 2026-02-20

> **Note:** This project is pre-implementation. No source code exists yet. All integrations below are derived from design artifacts: `/context/ERD/ERD.sql`, application design screenshots in `/context/Application Design/Application Design Screenshots/`, and project scope/design documents.

## APIs & External Services

**Cloud Cost & Billing APIs:**
- AWS Cost Explorer / Billing API - Primary cloud cost data source
  - SDK/Client: `@aws-sdk/client-cost-explorer`, `@aws-sdk/client-ce`
  - Auth: IAM Role-based (no stored access keys per design decision US-001 in Initial Setup screenshot); role ARN stored in `CLOUD_ACCOUNT.encrypted_credentials`
  - Sync: Real-time and scheduled; sync status tracked in `CLOUD_ACCOUNT.last_sync`

- Microsoft Azure Cost Management API - Secondary cloud cost source
  - SDK/Client: `@azure/arm-consumption` or Azure Cost Management SDK
  - Auth: Azure Service Principal credentials (stored encrypted in `CLOUD_ACCOUNT.encrypted_credentials`)
  - Sync: On-demand and scheduled (`CLOUD_ACCOUNT.last_sync`); "syncing" status shown in Cloud Providers design screenshot

- Google Cloud Platform Billing API - Tertiary cloud cost source
  - SDK/Client: `@google-cloud/billing`
  - Auth: GCP Service Account credentials (stored encrypted in `CLOUD_ACCOUNT.encrypted_credentials`)
  - Sync: Scheduled and manual trigger

> Cloud provider endpoints and API versions are stored per-provider in `CLOUD_PROVIDER.api_endpoint` and `CLOUD_PROVIDER.api_version`.

**Cloud Resource Management APIs (for Optimization Actions):**
- AWS EC2 API - Apply right-sizing recommendations (resize or terminate instances)
  - Auth: Same IAM Role as billing integration
  - Triggered by: `OPTIMIZATION_ACTION` records with `action_status = 'approved'`

- AWS RDS API - Database instance right-sizing
  - Same auth as above

- Azure Resource Manager API - Azure resource lifecycle actions
  - Same auth as Azure Cost Management

## Data Storage

**Databases:**
- Type/Provider: PostgreSQL (PL/pgSQL confirmed by trigger syntax in `/context/ERD/ERD.sql`)
  - Connection: Environment variable (e.g., `DATABASE_URL`)
  - ORM/Client: TBD - Prisma or Drizzle recommended given TypeScript stack
  - Schema: 20 tables defined in `/context/ERD/ERD.sql`
  - Key data: billing records, usage metrics, ML predictions, audit logs, compliance violations

**File Storage:**
- Report exports required (PDF, Excel, CSV, JSON per `REPORT_TEMPLATE.output_format` in ERD)
- Storage target TBD - local filesystem for development; object storage (S3 or equivalent) for production

**Caching:**
- Not defined yet; dashboard "real-time" requirement implies a cache layer will be needed for billing aggregates (Redis recommended)

## Authentication & Identity

**Auth Provider:**
- Custom user management (users stored in `USER` table in ERD with roles: `admin`, `devops`, `finance`, `auditor`, `viewer`)
- Specific auth provider TBD - JWT-based session management or an auth service (e.g., Auth0, Clerk, NextAuth.js)
- Role-based access control required: Finance sees budget focus, DevOps sees resource focus (per dashboard design decision US-004)

**Cloud Provider Auth:**
- AWS: IAM Role assumption (no long-lived access keys stored per design decision US-001)
- Azure: Service Principal with client credentials
- GCP: Service Account key (stored encrypted in database column `CLOUD_ACCOUNT.encrypted_credentials`)

## Monitoring & Observability

**Error Tracking:**
- Not specified in design documents

**Logs:**
- Application has a built-in `AUDIT_LOG` table (see `/context/ERD/ERD.sql`) storing user actions with `before_state`/`after_state` JSON, IP address, and user agent
- Infrastructure-level logging provider TBD

## Notification Services

**Alert Channels (from Budgets & Alerts design screenshot - US-007):**
- Email - Budget threshold alerts; `SCHEDULED_REPORT.recipient_emails` field in ERD; delivery provider TBD (SendGrid, SES, Resend)
- Slack - Budget/anomaly alerts; shown in "Recent Alert History" as notification channel
  - SDK: `@slack/web-api` or incoming webhook
- PagerDuty - Critical budget alert escalation; shown in "Recent Alert History"
  - SDK: `node-pagerduty` or Events API v2

**Alert Types (from `ALERT` table in ERD):**
- `budget` - spend threshold breaches
- `anomaly` - ML-detected spending anomalies
- `threshold` - metric threshold crossings
- `compliance` - policy violation alerts

## CI/CD & Deployment

**Hosting:**
- TBD - Not specified in design documents

**CI Pipeline:**
- None configured yet (no CI config files present)

## Webhooks & Callbacks

**Incoming:**
- None defined yet - cloud provider webhook endpoints may be needed for real-time billing event delivery

**Outgoing:**
- Alert notifications to Slack (webhook or API)
- PagerDuty Events API (outgoing HTTP POST for incidents)
- Email delivery via provider (outgoing SMTP or API calls)

## Scheduled Jobs (from ERD)

The `SCHEDULED_REPORT` table defines:
- Frequencies: `daily`, `weekly`, `monthly`, `quarterly`
- Output: PDF/Excel/CSV/JSON reports emailed to `recipient_emails`
- Fields: `last_run`, `next_run`, `schedule_time` (cron-style)
- Requires a job runner: node-cron, BullMQ, or a managed scheduler

The `OPTIMIZATION_ACTION` table supports scheduled execution:
- `scheduled_at` / `executed_at` fields imply deferred/async job execution
- Approval workflow before execution (`requires_approval` on `OPTIMIZATION_RULE`)

## Compliance Framework References

The `COMPLIANCE_POLICY` table references external compliance frameworks as string identifiers (no external API integration — policies are managed internally):
- `SOC2`
- `HIPAA`
- `GDPR`
- `PCI-DSS`
- `ISO27001`

These are shown in the Compliance & Governance design screenshot with active policy counts and violation tracking.

## Environment Configuration

**Required environment variables (anticipated):**
- `DATABASE_URL` - PostgreSQL connection string
- `SESSION_SECRET` / `JWT_SECRET` - Auth signing key
- `SLACK_WEBHOOK_URL` or `SLACK_BOT_TOKEN` - Slack alerts
- `PAGERDUTY_API_KEY` - PagerDuty escalation
- `EMAIL_PROVIDER_API_KEY` - Transactional email
- `ENCRYPTION_KEY` - For encrypting `CLOUD_ACCOUNT.encrypted_credentials`
- Cloud provider credentials injected at runtime via IAM roles (AWS) or environment secrets (Azure/GCP)

**Secrets location:**
- `.env` file (not yet created); production secrets via platform secret manager (TBD)

---

*Integration audit: 2026-02-20*
