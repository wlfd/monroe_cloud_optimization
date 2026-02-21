# CloudCost — Architecture Design Document

**Product:** CloudCost — Cloud Infrastructure Cost Optimization Platform
**Version:** 1.0
**Date:** February 2026
**For:** Development implementation reference (CloudCost MVP)

---

## Table of Contents

1. System Overview
2. Project Folder Structure
3. Database Schema (Full)
4. API Endpoint Catalog
5. Background Job Definitions
6. Azure Ingestion Design
7. Anomaly Detection Algorithm
8. LLM Integration Design
9. Multi-Tenant Attribution Design
10. Authentication & Authorization
11. Notification System Design
12. Environment Variables Reference
13. Local Development Setup
14. Production Deployment on Azure

---

## 1. System Overview

CloudCost is a **modular monolith** built with Python/FastAPI on the backend and React/TypeScript on the frontend. All modules are deployed as a single application to Azure Container Apps. Background jobs (ingestion, anomaly detection, attribution, recommendations) run as Celery workers on a separate container.

```
┌─────────────────────────────────────────────────────────────┐
│                        Users (Browser)                       │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTPS
┌────────────────────────▼────────────────────────────────────┐
│             React Frontend (Azure Static Web Apps)           │
│             TypeScript + shadcn/ui + Recharts                │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API (JSON)
┌────────────────────────▼────────────────────────────────────┐
│           FastAPI Application (Azure Container App)          │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ingestion │ │monitoring│ │ budgets  │ │   anomaly    │  │
│  │ module   │ │  module  │ │  module  │ │   module     │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │recommend.│ │attribut. │ │  audit   │ │    users/    │  │
│  │  module  │ │  module  │ │  module  │ │  api_keys    │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │
└────────────────────────┬────────────────────────────────────┘
          │              │                    │
          │         ┌────▼────┐               │
          │         │  Redis  │               │
          │         │(cache + │               │
          │         │ broker) │               │
          │         └────┬────┘               │
          │              │                    │
┌─────────▼──────────────▼────────────────────▼──────────────┐
│                   PostgreSQL 15                               │
│            (Azure Database for PostgreSQL)                   │
└─────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│        Celery Worker (Azure Container App)                   │
│        + Celery Beat Scheduler (Azure Container App)         │
│                                                              │
│  ingest → detect anomalies → check budgets (every 4h)       │
│  attribute tenants → generate recommendations (daily)        │
└─────────────────────────────────────────────────────────────┘
          │
┌─────────▼──────────────────────────────────────────────────┐
│              External Services                               │
│  Azure Cost Management API  │  Azure OpenAI  │  Anthropic   │
│  Azure Key Vault            │  SMTP (email)  │  (fallback)  │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Project Folder Structure

```
cloudcost/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app factory
│   │   ├── core/
│   │   │   ├── config.py              # Settings (pydantic-settings)
│   │   │   ├── database.py            # SQLAlchemy engine + session
│   │   │   ├── security.py            # JWT, bcrypt, AES-256 helpers
│   │   │   ├── dependencies.py        # FastAPI dependency injection
│   │   │   └── exceptions.py          # Custom HTTP exceptions
│   │   ├── models/                    # SQLAlchemy ORM models (one file per entity group)
│   │   │   ├── user.py                # user, user_session, api_key
│   │   │   ├── cloud.py               # cloud_provider, cloud_account, ingestion_run
│   │   │   ├── billing.py             # resource, billing_data, billing_tag
│   │   │   ├── budget.py              # budget, budget_threshold, alert_event
│   │   │   ├── notification.py        # notification_channel, notification_delivery
│   │   │   ├── anomaly.py             # anomaly, anomaly_resource
│   │   │   ├── recommendation.py      # optimization_recommendation, llm_cache
│   │   │   ├── attribution.py         # tenant, allocation_rule, resource_tenant_mapping, tenant_cost_allocation
│   │   │   └── audit.py               # audit_log
│   │   ├── schemas/                   # Pydantic request/response schemas
│   │   │   ├── user.py
│   │   │   ├── cloud.py
│   │   │   ├── billing.py
│   │   │   ├── budget.py
│   │   │   ├── anomaly.py
│   │   │   ├── recommendation.py
│   │   │   ├── attribution.py
│   │   │   └── audit.py
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── router.py          # Aggregate all v1 routers
│   │   │       ├── auth.py            # /auth endpoints
│   │   │       ├── costs.py           # /costs endpoints
│   │   │       ├── budgets.py         # /budgets endpoints
│   │   │       ├── anomalies.py       # /anomalies endpoints
│   │   │       ├── recommendations.py # /recommendations endpoints
│   │   │       ├── tenants.py         # /tenants endpoints
│   │   │       ├── audit.py           # /audit endpoints
│   │   │       ├── admin.py           # /admin endpoints
│   │   │       └── health.py          # /health endpoint
│   │   ├── services/                  # Business logic layer
│   │   │   ├── azure_ingestion.py     # Azure Cost Management API client
│   │   │   ├── cost_service.py        # Cost query and aggregation logic
│   │   │   ├── budget_service.py      # Budget evaluation and alerting
│   │   │   ├── anomaly_service.py     # Anomaly detection algorithm
│   │   │   ├── recommendation_service.py  # LLM prompt builder + response parser
│   │   │   ├── attribution_service.py # Tenant cost attribution processor
│   │   │   ├── notification_service.py # Email + webhook delivery
│   │   │   ├── audit_service.py       # Audit log writer
│   │   │   └── llm_client.py          # Azure OpenAI + Anthropic abstraction
│   │   └── tasks/
│   │       ├── celery_app.py          # Celery app + beat schedule config
│   │       ├── ingestion_tasks.py     # Task: ingest_billing_data
│   │       ├── anomaly_tasks.py       # Task: run_anomaly_detection
│   │       ├── budget_tasks.py        # Task: check_budget_thresholds
│   │       ├── attribution_tasks.py   # Task: run_tenant_attribution
│   │       ├── recommendation_tasks.py # Task: generate_recommendations
│   │       └── maintenance_tasks.py   # Tasks: expire_llm_cache, api_key_reminders, retry_webhooks
│   ├── migrations/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── conftest.py                # pytest fixtures (test DB, mock Azure client)
│   │   ├── test_ingestion.py
│   │   ├── test_anomaly.py
│   │   ├── test_budget.py
│   │   ├── test_attribution.py
│   │   ├── test_recommendations.py
│   │   └── test_api/                  # API route tests
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── Dockerfile
│   └── Dockerfile.worker
├── frontend/
│   ├── src/
│   │   ├── app/                       # Page-level components + routing
│   │   │   ├── layout.tsx
│   │   │   ├── dashboard/
│   │   │   ├── costs/
│   │   │   ├── budgets/
│   │   │   ├── anomalies/
│   │   │   ├── recommendations/
│   │   │   ├── tenants/
│   │   │   ├── audit/
│   │   │   └── admin/
│   │   ├── components/                # Shared UI components
│   │   │   ├── charts/
│   │   │   ├── tables/
│   │   │   └── ui/                    # shadcn/ui wrappers
│   │   ├── hooks/                     # Custom React hooks
│   │   ├── services/                  # API client functions (axios/fetch wrappers)
│   │   │   └── api.ts
│   │   ├── store/                     # React context / Zustand store
│   │   ├── types/                     # TypeScript type definitions
│   │   └── utils/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml                 # Local dev: app + worker + beat + redis + postgres
├── docker-compose.prod.yml            # Prod overrides
├── .env.example                       # All required environment variables with descriptions
├── .github/
│   └── workflows/
│       ├── test.yml                   # PR: pytest + ruff + mypy + frontend type-check
│       └── deploy.yml                 # Main branch: build + push to ACR + deploy to ACA
└── README.md
```

---

## 3. Database Schema (Full)

### Naming conventions
- All tables use `snake_case`
- All primary keys are `id UUID DEFAULT gen_random_uuid()`
- All timestamps are `TIMESTAMP WITH TIME ZONE` in UTC
- `created_at` defaults to `NOW()` on all tables
- Soft-delete pattern: `is_active BOOLEAN DEFAULT true` (no hard deletes on most tables)

---

### users

```sql
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,           -- bcrypt hash
    full_name   VARCHAR(255),
    role        VARCHAR(50) NOT NULL               -- 'admin' | 'devops' | 'finance' | 'viewer'
                CHECK (role IN ('admin', 'devops', 'finance', 'viewer')),
    is_active   BOOLEAN NOT NULL DEFAULT true,
    failed_login_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TIMESTAMP WITH TIME ZONE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_login  TIMESTAMP WITH TIME ZONE
);
```

### user_sessions

```sql
CREATE TABLE user_sessions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) NOT NULL UNIQUE,      -- SHA-256 of refresh token
    ip_address  INET,
    user_agent  TEXT,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked     BOOLEAN NOT NULL DEFAULT false,
    revoked_at  TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_token_hash ON user_sessions(token_hash);
```

### api_keys

```sql
CREATE TABLE api_keys (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_hash     VARCHAR(255) NOT NULL UNIQUE,     -- SHA-256 of full API key
    key_prefix   VARCHAR(8) NOT NULL,              -- First 8 chars for display (e.g., "cc_abc123")
    name         VARCHAR(255) NOT NULL,
    owner_user_id UUID NOT NULL REFERENCES users(id),
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at   TIMESTAMP WITH TIME ZONE NOT NULL, -- created_at + 90 days
    last_used_at TIMESTAMP WITH TIME ZONE,
    rotation_reminder_sent BOOLEAN NOT NULL DEFAULT false
);
```

### cloud_providers

```sql
CREATE TABLE cloud_providers (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    provider_type VARCHAR(50) NOT NULL DEFAULT 'azure'
                 CHECK (provider_type IN ('azure')),
    created_by   UUID REFERENCES users(id),
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### cloud_accounts

```sql
CREATE TABLE cloud_accounts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id          UUID NOT NULL REFERENCES cloud_providers(id),
    display_name         VARCHAR(255) NOT NULL,
    subscription_id      VARCHAR(255) NOT NULL,    -- Azure Subscription GUID
    azure_tenant_id      VARCHAR(255) NOT NULL,    -- Azure AD Tenant GUID
    client_id            VARCHAR(255) NOT NULL,    -- Service Principal App ID
    encrypted_client_secret TEXT NOT NULL,          -- AES-256 encrypted
    is_active            BOOLEAN NOT NULL DEFAULT true,
    sync_schedule_hours  INTEGER NOT NULL DEFAULT 4,
    last_sync_at         TIMESTAMP WITH TIME ZONE,
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by           UUID REFERENCES users(id)
);
```

### ingestion_runs

```sql
CREATE TABLE ingestion_runs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   UUID NOT NULL REFERENCES cloud_accounts(id),
    started_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    status       VARCHAR(20) NOT NULL DEFAULT 'running'
                 CHECK (status IN ('running', 'success', 'failed', 'partial')),
    rows_ingested INTEGER,
    data_from    DATE,                             -- Billing date range pulled
    data_to      DATE,
    error_message TEXT,
    retry_count  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_ingestion_runs_account_id ON ingestion_runs(account_id);
CREATE INDEX idx_ingestion_runs_started_at ON ingestion_runs(started_at DESC);
```

### resources

```sql
CREATE TABLE resources (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id       UUID NOT NULL REFERENCES cloud_accounts(id),
    azure_resource_id TEXT NOT NULL,               -- Full ARM resource ID
    name             VARCHAR(500),
    resource_type    VARCHAR(255),                 -- e.g., "Microsoft.Compute/virtualMachines"
    resource_group   VARCHAR(255),
    region           VARCHAR(100),
    subscription_id  VARCHAR(255),
    tags             JSONB NOT NULL DEFAULT '{}',
    first_seen_at    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_seen_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(account_id, azure_resource_id)
);
CREATE INDEX idx_resources_account_id ON resources(account_id);
CREATE INDEX idx_resources_resource_group ON resources(resource_group);
CREATE INDEX idx_resources_tags ON resources USING GIN(tags);
```

### billing_data

```sql
CREATE TABLE billing_data (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        UUID NOT NULL REFERENCES cloud_accounts(id),
    resource_id       UUID REFERENCES resources(id),
    service_name      VARCHAR(255) NOT NULL,        -- e.g., "Virtual Machines"
    resource_group    VARCHAR(255),
    subscription_id   VARCHAR(255),
    billing_date      DATE NOT NULL,
    billing_period    VARCHAR(7) NOT NULL,           -- "YYYY-MM"
    cost_usd          DECIMAL(18, 6) NOT NULL,
    usage_quantity    DECIMAL(18, 6),
    usage_unit        VARCHAR(100),
    meter_name        VARCHAR(255),
    meter_category    VARCHAR(255),
    tags              JSONB NOT NULL DEFAULT '{}',
    ingestion_run_id  UUID REFERENCES ingestion_runs(id),
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
-- billing_data is append-only; no UPDATEs or DELETEs
CREATE INDEX idx_billing_data_account_date ON billing_data(account_id, billing_date);
CREATE INDEX idx_billing_data_billing_period ON billing_data(billing_period);
CREATE INDEX idx_billing_data_service ON billing_data(service_name, billing_period);
CREATE INDEX idx_billing_data_resource_group ON billing_data(resource_group);
CREATE INDEX idx_billing_data_tags ON billing_data USING GIN(tags);
```

### billing_tags (denormalized for fast filtering)

```sql
CREATE TABLE billing_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    billing_data_id UUID NOT NULL REFERENCES billing_data(id) ON DELETE CASCADE,
    tag_key         VARCHAR(255) NOT NULL,
    tag_value       VARCHAR(255),
    billing_period  VARCHAR(7) NOT NULL
);
CREATE INDEX idx_billing_tags_key_value ON billing_tags(tag_key, tag_value);
CREATE INDEX idx_billing_tags_billing_period ON billing_tags(billing_period);
```

### budgets

```sql
CREATE TABLE budgets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   UUID NOT NULL REFERENCES cloud_accounts(id),
    name         VARCHAR(255) NOT NULL,
    scope_type   VARCHAR(50) NOT NULL
                 CHECK (scope_type IN ('subscription', 'resource_group', 'service', 'tag')),
    scope_value  VARCHAR(500),                     -- The value (resource group name, tag key=value, etc.)
    amount_usd   DECIMAL(18, 2) NOT NULL,
    period       VARCHAR(20) NOT NULL DEFAULT 'monthly'
                 CHECK (period IN ('monthly', 'annual')),
    start_date   DATE NOT NULL,
    end_date     DATE,
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_by   UUID REFERENCES users(id),
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### budget_thresholds

```sql
CREATE TABLE budget_thresholds (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id             UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    threshold_percent     INTEGER NOT NULL CHECK (threshold_percent > 0 AND threshold_percent <= 200),
    notification_channel_id UUID REFERENCES notification_channels(id),
    last_triggered_at     TIMESTAMP WITH TIME ZONE,
    last_triggered_period VARCHAR(7)                -- Prevent re-firing in same billing period
);
```

### alert_events

```sql
CREATE TABLE alert_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id           UUID NOT NULL REFERENCES budgets(id),
    threshold_id        UUID REFERENCES budget_thresholds(id),
    triggered_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    billing_period      VARCHAR(7) NOT NULL,
    spend_at_trigger    DECIMAL(18, 2) NOT NULL,
    budget_amount       DECIMAL(18, 2) NOT NULL,
    threshold_percent   INTEGER NOT NULL,
    delivery_status     VARCHAR(20) DEFAULT 'pending'
                        CHECK (delivery_status IN ('pending', 'delivered', 'failed'))
);
CREATE INDEX idx_alert_events_budget_id ON alert_events(budget_id);
CREATE INDEX idx_alert_events_triggered_at ON alert_events(triggered_at DESC);
```

### notification_channels

```sql
CREATE TABLE notification_channels (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    channel_type VARCHAR(20) NOT NULL CHECK (channel_type IN ('email', 'webhook')),
    config_json  JSONB NOT NULL,
    -- email: {"address": "ops@fileread.com"}
    -- webhook: {"url": "https://...", "secret": "hmac_secret"}
    owner_user_id UUID REFERENCES users(id),
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### notification_deliveries

```sql
CREATE TABLE notification_deliveries (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id     UUID NOT NULL REFERENCES notification_channels(id),
    event_type     VARCHAR(100) NOT NULL,           -- 'budget_alert' | 'anomaly_detected' | 'recommendation_ready'
    event_id       UUID NOT NULL,                  -- FK to the triggering entity (alert_event, anomaly, etc.)
    attempt_number INTEGER NOT NULL DEFAULT 1,
    attempted_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    status         VARCHAR(20) NOT NULL CHECK (status IN ('delivered', 'failed', 'pending')),
    response_code  INTEGER,
    error_message  TEXT
);
CREATE INDEX idx_notification_deliveries_event ON notification_deliveries(event_type, event_id);
CREATE INDEX idx_notification_deliveries_status ON notification_deliveries(status) WHERE status = 'failed';
```

### anomalies

```sql
CREATE TABLE anomalies (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id              UUID NOT NULL REFERENCES cloud_accounts(id),
    service_name            VARCHAR(255),
    resource_group          VARCHAR(255),
    anomaly_type            VARCHAR(50) NOT NULL DEFAULT 'spend_spike'
                            CHECK (anomaly_type IN ('spend_spike', 'new_service', 'trend_increase')),
    detected_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    detection_date          DATE NOT NULL,
    baseline_daily_avg_usd  DECIMAL(18, 4),
    actual_daily_spend_usd  DECIMAL(18, 4) NOT NULL,
    deviation_percent       DECIMAL(8, 2),
    severity                VARCHAR(20) NOT NULL
                            CHECK (severity IN ('critical', 'high', 'medium')),
    estimated_monthly_impact_usd DECIMAL(18, 2),
    status                  VARCHAR(20) NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'expected', 'dismissed')),
    status_reason           TEXT,
    resolved_by_user_id     UUID REFERENCES users(id),
    resolved_at             TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_anomalies_account_status ON anomalies(account_id, status);
CREATE INDEX idx_anomalies_detected_at ON anomalies(detected_at DESC);
```

### anomaly_resources

```sql
CREATE TABLE anomaly_resources (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    anomaly_id  UUID NOT NULL REFERENCES anomalies(id) ON DELETE CASCADE,
    resource_id UUID REFERENCES resources(id),
    resource_name VARCHAR(500),
    cost_delta_usd DECIMAL(18, 4)
);
CREATE INDEX idx_anomaly_resources_anomaly_id ON anomaly_resources(anomaly_id);
```

### optimization_recommendations

```sql
CREATE TABLE optimization_recommendations (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id               UUID NOT NULL REFERENCES cloud_accounts(id),
    category                 VARCHAR(50) NOT NULL
                             CHECK (category IN ('right-sizing', 'idle-resources', 'reserved-instances', 'storage-tier', 'other')),
    title                    VARCHAR(500) NOT NULL,
    description              TEXT NOT NULL,
    recommended_action       TEXT NOT NULL,
    affected_resources       JSONB,                -- Array of resource IDs/names
    estimated_monthly_savings_usd DECIMAL(18, 2),
    confidence_score         INTEGER CHECK (confidence_score BETWEEN 0 AND 100),
    status                   VARCHAR(20) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'accepted', 'dismissed', 'deferred')),
    model_used               VARCHAR(100),
    prompt_version           VARCHAR(50),           -- For prompt iteration tracking
    generated_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actioned_by_user_id      UUID REFERENCES users(id),
    actioned_at              TIMESTAMP WITH TIME ZONE,
    defer_until              TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_recommendations_account_status ON optimization_recommendations(account_id, status);
CREATE INDEX idx_recommendations_generated_at ON optimization_recommendations(generated_at DESC);
```

### llm_cache

```sql
CREATE TABLE llm_cache (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key   VARCHAR(64) NOT NULL UNIQUE,        -- SHA-256 hex of (model + input context hash)
    model       VARCHAR(100) NOT NULL,
    response_json JSONB NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at  TIMESTAMP WITH TIME ZONE NOT NULL,  -- created_at + 24 hours
    hit_count   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_llm_cache_expires_at ON llm_cache(expires_at);
```

### tenants

```sql
CREATE TABLE tenants (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_name        VARCHAR(255) NOT NULL,
    tenant_identifier  VARCHAR(255) NOT NULL UNIQUE, -- The value used in Azure tags (e.g., customer slug)
    tag_key            VARCHAR(255) NOT NULL DEFAULT 'tenant_id',
    is_active          BOOLEAN NOT NULL DEFAULT true,
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by         UUID REFERENCES users(id)
);
```

### allocation_rules

```sql
CREATE TABLE allocation_rules (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id           UUID NOT NULL REFERENCES cloud_accounts(id),
    rule_name            VARCHAR(255) NOT NULL,
    description          TEXT,
    method               VARCHAR(30) NOT NULL
                         CHECK (method IN ('by_tenant_count', 'by_usage', 'manual_percent')),
    manual_splits_json   JSONB,                     -- {"tenant_id_1": 30.0, "tenant_id_2": 70.0}
    applies_to           VARCHAR(50) DEFAULT 'untagged', -- 'untagged' | 'resource_group:name' | 'service:name'
    applies_to_value     VARCHAR(255),
    is_active            BOOLEAN NOT NULL DEFAULT true,
    effective_from       DATE NOT NULL,
    created_by           UUID REFERENCES users(id),
    created_at           TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

### resource_tenant_mappings

```sql
CREATE TABLE resource_tenant_mappings (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_id        UUID NOT NULL REFERENCES resources(id),
    tenant_id          UUID NOT NULL REFERENCES tenants(id),
    mapping_source     VARCHAR(20) NOT NULL CHECK (mapping_source IN ('tag', 'rule')),
    allocation_rule_id UUID REFERENCES allocation_rules(id),
    allocation_percent DECIMAL(5, 2) NOT NULL DEFAULT 100.0,  -- Fraction if shared
    effective_from     DATE NOT NULL,
    effective_to       DATE,
    created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_resource_tenant_resource ON resource_tenant_mappings(resource_id);
CREATE INDEX idx_resource_tenant_tenant ON resource_tenant_mappings(tenant_id);
```

### tenant_cost_allocations

```sql
CREATE TABLE tenant_cost_allocations (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id                  UUID NOT NULL REFERENCES tenants(id),
    account_id                 UUID NOT NULL REFERENCES cloud_accounts(id),
    billing_period             VARCHAR(7) NOT NULL,    -- "YYYY-MM"
    total_cost_usd             DECIMAL(18, 4) NOT NULL,
    direct_cost_usd            DECIMAL(18, 4) NOT NULL, -- From directly tagged resources
    allocated_shared_cost_usd  DECIMAL(18, 4) NOT NULL, -- From allocation rules
    run_at                     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, account_id, billing_period)
);
CREATE INDEX idx_tenant_cost_allocations_tenant_period ON tenant_cost_allocations(tenant_id, billing_period);
```

### audit_log

```sql
CREATE TABLE audit_log (
    id           BIGSERIAL PRIMARY KEY,              -- Sequential integer for ordering guarantees
    event_id     UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    timestamp    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    actor_type   VARCHAR(20) NOT NULL CHECK (actor_type IN ('user', 'system', 'api_key')),
    actor_id     VARCHAR(255),                       -- UUID of user/api_key, or system task name
    action_type  VARCHAR(100) NOT NULL,              -- e.g., 'budget.created', 'user.login', 'ingestion.completed'
    entity_type  VARCHAR(100),                       -- e.g., 'budget', 'user', 'anomaly'
    entity_id    VARCHAR(255),                       -- UUID of affected entity
    before_state JSONB,                              -- State before change
    after_state  JSONB,                              -- State after change
    ip_address   INET,
    request_id   VARCHAR(255),                       -- HTTP request trace ID
    metadata     JSONB                               -- Any additional context
);
-- audit_log is append-only. Enforce via PostgreSQL trigger:
-- CREATE RULE no_update_audit_log AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
-- CREATE RULE no_delete_audit_log AS ON DELETE TO audit_log DO INSTEAD NOTHING;
CREATE INDEX idx_audit_log_timestamp ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_log_actor ON audit_log(actor_type, actor_id);
CREATE INDEX idx_audit_log_action_type ON audit_log(action_type);
CREATE INDEX idx_audit_log_entity ON audit_log(entity_type, entity_id);
```

---

## 4. API Endpoint Catalog

**Base URL:** `/api/v1`
**Auth:** All endpoints except `/auth/login` and `/health` require `Authorization: Bearer <JWT>` or `X-API-Key: <key>` header.
**Rate limit:** 100 req/min per API key; 200 req/min for JWT sessions.
**OpenAPI docs:** Available at `/api/docs` (Swagger UI) and `/api/redoc`.

---

### Auth (`/auth`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/login` | None | Email + password → access token + refresh token |
| POST | `/auth/refresh` | Refresh token | Rotate access token |
| POST | `/auth/logout` | JWT | Revoke current refresh token |
| GET | `/auth/me` | JWT | Get current user profile |

**POST /auth/login** Request:
```json
{"email": "admin@fileread.com", "password": "..."}
```
Response:
```json
{"access_token": "eyJ...", "refresh_token": "...", "expires_in": 3600, "user": {"id": "...", "email": "...", "role": "admin"}}
```

---

### Costs (`/costs`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/costs/summary` | JWT/Key | MTD total, projected month-end, previous period comparison |
| GET | `/costs/daily` | JWT/Key | Daily spend time series (supports `?days=30\|60\|90` and `?from=&to=`) |
| GET | `/costs/breakdown` | JWT/Key | Spend grouped by dimension (`?group_by=service\|resource_group\|region\|tag&tag_key=...`) |
| GET | `/costs/top-resources` | JWT/Key | Top N most expensive resources (`?limit=10&period=YYYY-MM`) |
| GET | `/costs/resources/{resource_id}` | JWT/Key | Single resource cost detail |
| GET | `/costs/export` | JWT/Key | Export cost breakdown to CSV download |
| GET | `/costs/accounts/{account_id}/summary` | JWT/Key | Summary scoped to a specific Azure subscription |

---

### Budgets (`/budgets`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/budgets` | JWT | List all budgets with current spend vs. amount |
| POST | `/budgets` | JWT (admin/finance) | Create a new budget |
| GET | `/budgets/{id}` | JWT | Budget detail with threshold status |
| PUT | `/budgets/{id}` | JWT (admin/finance) | Update budget amount, period, or name |
| DELETE | `/budgets/{id}` | JWT (admin) | Soft-delete a budget |
| POST | `/budgets/{id}/thresholds` | JWT (admin/finance) | Add a threshold to a budget |
| DELETE | `/budgets/{id}/thresholds/{threshold_id}` | JWT (admin) | Remove a threshold |
| GET | `/budgets/{id}/alerts` | JWT | Alert history for a budget |

---

### Anomalies (`/anomalies`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/anomalies` | JWT/Key | List anomalies (`?status=active\|expected\|dismissed&severity=critical\|high\|medium`) |
| GET | `/anomalies/{id}` | JWT/Key | Anomaly detail with affected resources |
| PATCH | `/anomalies/{id}/status` | JWT | Update status to 'expected' or 'dismissed' |
| GET | `/anomalies/summary` | JWT/Key | Count by severity and status for dashboard widget |

---

### Recommendations (`/recommendations`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/recommendations` | JWT/Key | List recommendations (`?status=pending\|accepted\|dismissed&category=...`) |
| GET | `/recommendations/{id}` | JWT/Key | Recommendation detail |
| PATCH | `/recommendations/{id}/action` | JWT | Set status: accepted, dismissed, deferred (`?defer_until=ISO8601`) |
| POST | `/recommendations/generate` | JWT (admin) | Manually trigger recommendation generation |
| GET | `/recommendations/savings-summary` | JWT/Key | Total accepted savings, pending opportunity |

---

### Tenants (`/tenants`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/tenants` | JWT | List all tenants |
| POST | `/tenants` | JWT (admin) | Create a tenant |
| GET | `/tenants/{id}` | JWT | Tenant detail |
| PUT | `/tenants/{id}` | JWT (admin) | Update tenant name or identifier |
| GET | `/tenants/{id}/costs` | JWT/Key | Monthly costs for a tenant (`?from=YYYY-MM&to=YYYY-MM`) |
| GET | `/tenants/{id}/costs/export` | JWT | Export tenant cost history to CSV |
| GET | `/tenants/costs/summary` | JWT/Key | All tenants cost summary for current billing period |
| GET | `/allocation-rules` | JWT (admin) | List allocation rules |
| POST | `/allocation-rules` | JWT (admin) | Create allocation rule |
| PUT | `/allocation-rules/{id}` | JWT (admin) | Update allocation rule |

---

### Admin (`/admin`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/admin/users` | JWT (admin) | List all users |
| POST | `/admin/users` | JWT (admin) | Create a user |
| PUT | `/admin/users/{id}` | JWT (admin) | Update user role or active status |
| GET | `/admin/accounts` | JWT (admin) | List Azure accounts |
| POST | `/admin/accounts` | JWT (admin) | Add Azure subscription (provider config) |
| PUT | `/admin/accounts/{id}` | JWT (admin) | Update account credentials |
| DELETE | `/admin/accounts/{id}` | JWT (admin) | Deactivate account |
| GET | `/admin/api-keys` | JWT (admin) | List API keys for current user |
| POST | `/admin/api-keys` | JWT | Create a new API key (returns full key once) |
| DELETE | `/admin/api-keys/{id}` | JWT | Revoke an API key |
| GET | `/admin/ingestion-runs` | JWT (admin/devops) | Recent ingestion run history |
| POST | `/admin/ingestion-runs` | JWT (admin) | Trigger manual ingestion |
| GET | `/admin/notification-channels` | JWT (admin) | List notification channels |
| POST | `/admin/notification-channels` | JWT (admin) | Create email or webhook channel |
| DELETE | `/admin/notification-channels/{id}` | JWT (admin) | Delete channel |

---

### Audit (`/audit`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/audit/logs` | JWT (admin) | Query audit log (`?from=&to=&actor_id=&action_type=&entity_type=&page=&limit=`) |
| GET | `/audit/logs/export` | JWT (admin) | Export filtered audit log to CSV or JSON |

---

### Health (`/health`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/health` | None | Liveness check: `{"status": "ok", "version": "1.0.0"}` |
| GET | `/health/ready` | None | Readiness: checks DB + Redis connectivity |

---

## 5. Background Job Definitions

All jobs are implemented as Celery tasks in `app/tasks/`. The Celery beat scheduler runs on its own container.

### Job: ingest_billing_data
- **Schedule:** Every 4 hours (cron: `0 */4 * * *`)
- **Steps:**
  1. Query all active `cloud_accounts`
  2. For each account, decrypt `encrypted_client_secret` from Key Vault
  3. Authenticate with Azure MSAL using service principal
  4. Determine `last_successful_ingestion_date` from latest `ingestion_run`
  5. Call Azure Cost Management API (`/providers/Microsoft.CostManagement/query`) for date range since last run
  6. Normalize response → insert into `billing_data` (upsert by account + resource + date composite)
  7. Upsert `resources` table from billing data tags
  8. Insert flattened entries into `billing_tags`
  9. Create `ingestion_run` record with status + row count
  10. Write audit log entry
  11. On failure: retry up to 3 times with exponential backoff; after max retries send admin alert
- **Idempotency:** Upsert logic prevents duplicate billing records on re-run

### Job: run_anomaly_detection
- **Schedule:** Every 4 hours, 30 minutes after ingestion (cron: `30 */4 * * *`)
- **Steps:**
  1. For each active `cloud_account`:
  2. Aggregate `billing_data` to daily spend per `(service_name, resource_group)` for the last 31 days
  3. For each dimension pair, compute 30-day rolling mean and standard deviation
  4. Compare today's spend to baseline; flag if `deviation_percent >= threshold` (default 20%)
  5. Check for new services (first appearance in billing data)
  6. Calculate `estimated_monthly_impact = (actual - baseline) * remaining_days_in_month`
  7. Assign severity based on impact and deviation thresholds
  8. Insert new `anomaly` records (skip if duplicate detected_at + service within same day)
  9. For each new anomaly, query related resources and insert `anomaly_resource` records
  10. Trigger notifications for new anomalies via `notification_service`

### Job: check_budget_thresholds
- **Schedule:** Every 4 hours, 60 minutes after ingestion (cron: `0 1,5,9,13,17,21 * * *`)
- **Steps:**
  1. For each active `budget`:
  2. Calculate current period spend for budget scope (subscription/resource_group/service/tag)
  3. Calculate `spend_percent = current_spend / budget_amount * 100`
  4. For each `budget_threshold` not yet triggered in current billing period:
  5. If `spend_percent >= threshold_percent`: insert `alert_event` and enqueue notification

### Job: run_tenant_attribution
- **Schedule:** Daily at 02:00 UTC (cron: `0 2 * * *`)
- **Steps:**
  1. For each active `cloud_account`, for the current billing period:
  2. Query all `billing_data` for the period
  3. Join with `resource_tenant_mappings` to identify directly attributed costs
  4. Identify untagged/shared resources not covered by direct mappings
  5. Apply active `allocation_rules` to distribute shared costs proportionally
  6. Sum direct + allocated costs per tenant
  7. Upsert `tenant_cost_allocations` for the period
  8. Log attribution run in audit trail

### Job: generate_recommendations
- **Schedule:** Daily at 03:00 UTC (cron: `0 3 * * *`)
- **Steps:**
  1. Build a cost summary context: top 20 services by MTD spend, anomalies in last 7 days, resource type breakdown
  2. Hash the context to generate `cache_key`
  3. Check `llm_cache` for a hit; if found, skip LLM call
  4. Check daily call count against configured limit; if exceeded, skip and log warning
  5. Select model: if total anomaly impact > $500, use `gpt-4o`/`claude-sonnet-4-5`; else use `gpt-4o-mini`/`claude-haiku-4-5`
  6. Call LLM with structured prompt (see Section 8)
  7. Parse JSON response into `optimization_recommendation` records
  8. Store raw response in `llm_cache` with 24h TTL
  9. Insert new recommendations (skip if duplicate title + account within 7 days)

---

## 6. Azure Ingestion Design

### Authentication
- Use `azure-identity` Python SDK with `ClientSecretCredential`
- Credentials: `tenant_id`, `client_id`, `client_secret` (decrypted from DB at runtime)
- Required Azure role on subscription: `Cost Management Reader`

### API Calls
```
POST https://management.azure.com/subscriptions/{subscriptionId}/providers/Microsoft.CostManagement/query?api-version=2023-04-01

Body:
{
  "type": "ActualCost",
  "timeframe": "Custom",
  "timePeriod": {"from": "2026-01-01", "to": "2026-02-20"},
  "dataset": {
    "granularity": "Daily",
    "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
    "grouping": [
      {"type": "Dimension", "name": "ServiceName"},
      {"type": "Dimension", "name": "ResourceGroup"},
      {"type": "Dimension", "name": "ResourceId"},
      {"type": "TagKey", "name": "tenant_id"}
    ]
  }
}
```

### Rate Limit Handling
- Azure Cost Management API: 800 requests/hour per subscription
- Implement exponential backoff: wait 5s, 30s, 120s on 429 responses
- Log all retry attempts

### Historical Backfill
- On first setup, ingest data 24 months back in 1-month chunks to avoid API timeouts
- Mark as `is_historical_backfill=true` in `ingestion_run` for observability

---

## 7. Anomaly Detection Algorithm

```python
def detect_anomalies(account_id: UUID, detection_date: date, db: Session) -> list[Anomaly]:
    """
    For each (service_name, resource_group) combination with billing data:
    1. Get 30-day rolling daily costs ending yesterday
    2. Calculate baseline mean and standard deviation
    3. Get today's cost
    4. Calculate deviation
    5. Flag if deviation exceeds threshold and dollar impact is meaningful
    """
    DEVIATION_THRESHOLD = 0.20   # configurable per account
    MIN_DOLLAR_IMPACT = 100      # configurable, skip cheap anomalies

    # Step 1: Get 30-day baseline
    baseline_rows = db.query(
        func.avg(daily_cost).label('mean'),
        func.stddev(daily_cost).label('stddev'),
        service_name,
        resource_group
    ).filter(
        billing_date >= detection_date - timedelta(days=31),
        billing_date < detection_date
    ).group_by(service_name, resource_group).all()

    # Step 2: Get today's spend
    today_rows = db.query(...).filter(billing_date == detection_date).all()

    # Step 3: Compare
    for row in today_rows:
        baseline = get_baseline(row.service_name, row.resource_group, baseline_rows)
        if baseline.mean == 0:
            continue  # New service, handle separately

        deviation = (row.cost - baseline.mean) / baseline.mean
        remaining_days = days_in_month(detection_date) - detection_date.day
        estimated_monthly_impact = (row.cost - baseline.mean) * remaining_days

        if deviation >= DEVIATION_THRESHOLD and estimated_monthly_impact >= MIN_DOLLAR_IMPACT:
            severity = classify_severity(deviation, estimated_monthly_impact)
            # Create anomaly record...

    # Step 4: Detect new services
    new_services = [r for r in today_rows if r.service_name not in known_services_set]
    # Create 'new_service' type anomaly for each...

def classify_severity(deviation: float, impact_usd: float) -> str:
    if impact_usd > 1000 or deviation > 0.50:
        return 'critical'
    elif impact_usd > 500 or deviation > 0.30:
        return 'high'
    else:
        return 'medium'
```

---

## 8. LLM Integration Design

### Client Abstraction (`app/services/llm_client.py`)

```python
class LLMClient:
    """Abstracts Azure OpenAI and Anthropic; handles routing and fallback."""

    async def complete(self, prompt: str, context: dict, complexity: str = 'low') -> dict:
        model = self._select_model(complexity)
        cache_key = self._cache_key(model, context)

        # Check cache
        cached = await self._get_cache(cache_key)
        if cached:
            return cached

        # Check daily limit
        if not await self._check_daily_limit():
            raise LLMDailyLimitExceeded()

        # Try primary (Azure OpenAI), fallback to Anthropic
        try:
            result = await self._call_azure_openai(model, prompt)
        except Exception:
            result = await self._call_anthropic(model, prompt)

        await self._store_cache(cache_key, result)
        return result

    def _select_model(self, complexity: str) -> str:
        if complexity == 'high':
            return 'gpt-4o'   # or 'claude-sonnet-4-5' for Anthropic fallback
        return 'gpt-4o-mini'  # or 'claude-haiku-4-5'
```

### Recommendation Prompt Template

```
You are a cloud cost optimization expert. Analyze the following Azure billing data for a legal tech SaaS company and provide specific, actionable cost optimization recommendations.

BILLING SUMMARY (current month):
{billing_summary_json}

TOP SERVICES BY COST:
{top_services_json}

RECENT ANOMALIES:
{anomalies_json}

Respond with a JSON array of up to 5 recommendations. Each recommendation must follow this schema:
{
  "category": "right-sizing" | "idle-resources" | "reserved-instances" | "storage-tier" | "other",
  "title": "Short title (max 100 chars)",
  "description": "Plain-language explanation of the problem",
  "recommended_action": "Specific action to take",
  "affected_services": ["ServiceName1"],
  "estimated_monthly_savings_usd": 500.00,
  "confidence_score": 75,
  "confidence_rationale": "Why this confidence level"
}

Only include recommendations where you have sufficient data to justify a specific savings estimate.
```

---

## 9. Multi-Tenant Attribution Design

### Attribution Flow (Daily Job)

```
billing_data for period
         │
         ├── resources with tag tenant_id=X  ──► direct attribution to tenant X (100%)
         │
         └── resources without tenant tag
                    │
                    └── apply allocation_rule
                               │
                               ├── by_tenant_count: divide equally among all active tenants
                               ├── by_usage: divide proportional to direct usage costs
                               └── manual_percent: use manual_splits_json weights
```

### Untagged Resource Coverage Report
When attribution runs, compute and store:
- Total spend: `$X`
- Directly tagged: `$Y` (`Y/X * 100`%)
- Allocated via rules: `$Z`
- Unallocated (no rule coverage): `$(X-Y-Z)`

Surface the unallocated percentage in the admin UI to encourage better tagging.

---

## 10. Authentication & Authorization

### JWT Strategy
- Access token: 1 hour expiry, signed with `HS256` using `JWT_SECRET_KEY`
- Refresh token: 7 day expiry, stored hashed in `user_sessions`
- Payload: `{"sub": user_id, "role": "admin", "exp": timestamp, "jti": uuid}`

### RBAC Matrix

| Permission | admin | devops | finance | viewer |
|------------|-------|--------|---------|--------|
| View dashboards and costs | ✓ | ✓ | ✓ | ✓ |
| Export CSV reports | ✓ | ✓ | ✓ | ✗ |
| Manage budgets | ✓ | ✗ | ✓ | ✗ |
| Acknowledge anomalies | ✓ | ✓ | ✗ | ✗ |
| Accept/dismiss recommendations | ✓ | ✓ | ✗ | ✗ |
| View tenant attribution | ✓ | ✓ | ✓ | ✗ |
| Manage tenants and allocation rules | ✓ | ✗ | ✗ | ✗ |
| Manage Azure accounts | ✓ | ✗ | ✗ | ✗ |
| Manage users | ✓ | ✗ | ✗ | ✗ |
| View audit log | ✓ | ✗ | ✗ | ✗ |
| Trigger manual ingestion | ✓ | ✓ | ✗ | ✗ |
| Manage API keys | ✓ | ✓ | ✓ | ✗ |
| Manage notification channels | ✓ | ✗ | ✗ | ✗ |

### API Key Auth
- Keys are prefixed `cc_` followed by 32 random bytes (URL-safe base64)
- Stored as SHA-256 hash in `api_keys` table
- Full key shown only once at creation
- Rate limited independently from JWT sessions

---

## 11. Notification System Design

### Email (via SMTP)
- Library: `aiosmtplib` (async)
- Config: SMTP host, port, username, password via environment variables
- Templates: Jinja2 HTML templates per notification type
- Notification types: `budget_alert`, `anomaly_detected`, `ingestion_failed`, `api_key_expiring`

### Webhook (HTTP POST)
- Payload signed with HMAC-SHA256 using channel's secret (header: `X-CloudCost-Signature: sha256=...`)
- Payload structure:
```json
{
  "event_type": "budget.threshold_crossed",
  "event_id": "uuid",
  "timestamp": "ISO8601",
  "data": { ... event-specific fields ... }
}
```
- Retry policy: 3 attempts — immediately, +1 min, +5 min
- After 3 failures: mark delivery as failed; admin can view in notification delivery history

---

## 12. Environment Variables Reference

```bash
# Application
APP_ENV=development                    # development | production
APP_SECRET_KEY=...                     # Random 32-byte hex, used for JWT signing
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/cloudcost

# Redis
REDIS_URL=redis://localhost:6379/0

# Azure (for Azure Cost Management API)
# Note: Actual per-account credentials stored encrypted in DB; these are for app-level Azure access
AZURE_KEY_VAULT_URL=https://cloudcost-kv.vault.azure.net/
AZURE_CLIENT_ID=...                    # App registration client ID (for Key Vault access)
AZURE_CLIENT_SECRET=...               # App registration secret (for Key Vault access)
AZURE_TENANT_ID=...                    # Your Azure AD tenant

# Encryption
ENCRYPTION_KEY=...                     # 32-byte base64-encoded AES-256 key for credential encryption

# LLM
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT_MINI=gpt-4o-mini    # Deployment name for cheap model
AZURE_OPENAI_DEPLOYMENT_FULL=gpt-4o         # Deployment name for capable model
ANTHROPIC_API_KEY=...                        # Fallback
LLM_DAILY_CALL_LIMIT=100                    # Max LLM API calls per day across all jobs
LLM_CACHE_TTL_HOURS=24

# Email (SMTP)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=...
SMTP_FROM_ADDRESS=cloudcost@fileread.com
SMTP_FROM_NAME=CloudCost

# Frontend
VITE_API_BASE_URL=https://api.cloudcost.fileread.com/api/v1

# JWT
JWT_SECRET_KEY=...                     # Random 64-byte hex
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Feature flags
ENABLE_LLM_RECOMMENDATIONS=true
ANOMALY_DETECTION_ENABLED=true
INGESTION_SCHEDULE_HOURS=4
```

---

## 13. Local Development Setup

### Prerequisites
- Docker Desktop
- Python 3.11+ (for running tests outside Docker)
- Node.js 20+ (for frontend development)

### docker-compose.yml (local)

```yaml
version: '3.9'
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: cloudcost
      POSTGRES_USER: cloudcost
      POSTGRES_PASSWORD: localdev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    environment:
      DATABASE_URL: postgresql+asyncpg://cloudcost:localdev@db:5432/cloudcost
      REDIS_URL: redis://redis:6379/0
    env_file: .env.local
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
    depends_on:
      - db
      - redis

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A app.tasks.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://cloudcost:localdev@db:5432/cloudcost
      REDIS_URL: redis://redis:6379/0
    env_file: .env.local
    depends_on:
      - db
      - redis

  beat:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    command: celery -A app.tasks.celery_app beat --loglevel=info
    depends_on:
      - redis

  frontend:
    build:
      context: ./frontend
    command: npm run dev
    ports:
      - "3000:3000"
    volumes:
      - ./frontend/src:/app/src
    environment:
      VITE_API_BASE_URL: http://localhost:8000/api/v1

volumes:
  postgres_data:
```

### Quick start
```bash
cp .env.example .env.local
docker compose up -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_dev_data   # Optional: seed test data
# API: http://localhost:8000/api/docs
# Frontend: http://localhost:3000
```

---

## 14. Production Deployment on Azure

### Resource Topology

```
Azure Resource Group: rg-cloudcost-prod
│
├── Azure Static Web Apps        → React frontend (CDN-backed, free tier)
├── Azure Container Registry     → cloudcostacr.azurecr.io (Docker images)
├── Azure Container Apps Environment
│   ├── Container App: cloudcost-api         (FastAPI, min 1, max 3 replicas)
│   ├── Container App: cloudcost-worker      (Celery worker, 1 replica)
│   └── Container App: cloudcost-beat        (Celery beat, 1 replica)
├── Azure Database for PostgreSQL Flexible Server (General Purpose, 2 vCores)
├── Azure Cache for Redis        (Basic C1)
└── Azure Key Vault              (cloudcost-kv)
    ├── Secret: encryption-key
    ├── Secret: jwt-secret-key
    ├── Secret: azure-openai-api-key
    └── Secret: anthropic-api-key
```

### GitHub Actions CI/CD (`.github/workflows/deploy.yml`)
```
Trigger: push to main
Steps:
1. Run pytest (backend tests)
2. Run ruff lint + mypy type check
3. Run frontend tsc --noEmit
4. Build Docker image (backend)
5. Push to Azure Container Registry
6. Deploy to Azure Container Apps (az containerapp update)
7. Run database migrations (alembic upgrade head) via one-off container job
```

### CORS Configuration
FastAPI CORS middleware allows:
- `https://cloudcost.fileread.com` (production frontend)
- `http://localhost:3000` (local dev only if `APP_ENV=development`)

---

*Architecture Document v1.0 — February 2026*
*CloudCost MVP — Python/FastAPI + PostgreSQL + React + Celery*
