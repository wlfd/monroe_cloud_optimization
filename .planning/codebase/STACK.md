# Technology Stack

**Analysis Date:** 2026-02-20

> **Note:** This project is pre-implementation. No source code exists yet. All stack decisions below are derived from design artifacts in `/context/`: the ERD SQL schema (`/context/ERD/ERD.sql`), application design screenshots (`/context/Application Design/Application Design Screenshots/`), and project scope documents.

## Languages

**Primary:**
- TypeScript - Frontend and backend (implied by modern SaaS web app design patterns)
- SQL - PostgreSQL-dialect DDL in `/context/ERD/ERD.sql`

**Secondary:**
- Python - ML/anomaly detection engine (ML model tables present: `ML_MODEL`, `PREDICTION` in ERD; anomaly detection shown in design screenshots requiring statistical modeling)

## Runtime

**Environment:**
- Node.js - Web application server and API layer

**Package Manager:**
- Not yet determined - lockfile not present
- Recommended: `pnpm` or `npm`

## Frameworks

**Core:**
- React / Next.js (recommended) - SPA/SSR web application; design shows a multi-page SaaS dashboard with server-rendered data
- TailwindCSS (recommended) - Design screenshots show utility-class-style component layout

**Testing:**
- Not yet determined

**Build/Dev:**
- Not yet determined

## Key Dependencies (Planned/Required)

**Cloud Provider SDKs:**
- `@aws-sdk/client-cost-explorer` - AWS Cost Explorer API ingestion
- `@aws-sdk/client-ce` - AWS billing data
- `@azure/arm-consumption` - Azure cost management
- `@google-cloud/billing` - GCP billing data

**ML / Analytics:**
- scikit-learn or equivalent - ML model training for `forecast`, `anomaly`, `optimization` model types (see `ML_MODEL` table in ERD)
- A time-series anomaly detection library (e.g., Prophet, statsmodels)

**Data Visualization:**
- Chart library required - design screenshots show bar charts, progress bars, trend lines (e.g., Recharts, Chart.js, or Tremor)

**Infrastructure:**
- ORM for PostgreSQL (e.g., Prisma, Drizzle, or SQLAlchemy for Python layer)
- Job scheduler for `SCHEDULED_REPORT` table (cron-based, e.g., node-cron or BullMQ)
- Email delivery for `recipient_emails` in `SCHEDULED_REPORT` table

**Notification Integrations:**
- Slack SDK - Budget alerts show "Slack, Email, PagerDuty" notification channels (from Budgets & Alerts design screenshot)
- PagerDuty SDK - Same source

## Database

**Primary Database:**
- PostgreSQL - Confirmed by PL/pgSQL trigger syntax in `/context/ERD/ERD.sql` (uses `RETURNS TRIGGER AS $$ ... $$ LANGUAGE plpgsql`)
- 20 tables, 25+ indexes, 2 views, 10 auto-update triggers
- JSON columns used in: `RESOURCE.tags`, `PREDICTION.prediction_details`, `AUDIT_LOG.before_state`, `AUDIT_LOG.after_state`, `REPORT_TEMPLATE.template_config`

## Configuration

**Environment:**
- `.env` file expected (not present yet)
- Required variables will include: cloud provider credentials/role ARNs, database connection string, notification service tokens (Slack, PagerDuty)
- Design decision from Initial Setup screenshot: "IAM Role approach (no access keys stored)" for AWS credential handling

**Build:**
- No build config files present yet

## Platform Requirements

**Development:**
- Node.js runtime
- PostgreSQL instance
- Cloud provider credentials (AWS IAM Role, Azure Service Principal, GCP Service Account)

**Production:**
- Web application host (TBD)
- PostgreSQL-compatible managed database (e.g., AWS RDS, Supabase, Neon)
- Background job worker for scheduled reports and ML model runs
- Secure credential store for encrypted cloud account credentials (see `CLOUD_ACCOUNT.encrypted_credentials` column in ERD)

## Application Modules (from Design)

Based on navigation in design screenshots:
- `Dashboard` - Real-time cost overview, KPIs, anomaly alerts
- `Cloud Providers` - Multi-cloud account connection and sync management
- `Cost Breakdown` - Spend analysis by team/environment
- `Budgets & Alerts` - Budget CRUD and threshold alerting
- `Anomaly Detection` - ML-powered spend anomaly surface
- `Resource Optimization` - ML right-sizing recommendations
- `Compliance` - SOC2, HIPAA, GDPR, PCI-DSS policy enforcement
- `Audit Trail` - Immutable audit log viewer
- `Settings` - Org/user/provider configuration

---

*Stack analysis: 2026-02-20*
