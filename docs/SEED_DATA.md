# CloudCost — Seed Data & Test Fixture Reference

Generated from source on 2026-03-14. Derived from `backend/app/scripts/` and `backend/tests/`.

---

## Section 1: Admin User Seed (`seed_admin`)

### What it does

`seed_admin` creates the first administrative user in the `users` table. It is idempotent — if any row with `role = 'admin'` already exists, the script exits without making changes.

The user is created with:

| Column | Value |
|--------|-------|
| `email` | Value of `FIRST_ADMIN_EMAIL` env var |
| `password_hash` | Argon2 hash of `FIRST_ADMIN_PASSWORD` (via `pwdlib.PasswordHash.recommended()`) |
| `full_name` | `"Admin"` (literal string) |
| `role` | `"admin"` |
| `is_active` | `true` |
| `failed_login_attempts` | `0` (default) |
| `created_at` / `updated_at` | Current UTC time (set by `utcnow` column default) |

### Environment variables required

| Variable | Purpose |
|----------|---------|
| `FIRST_ADMIN_EMAIL` | Email address for the admin account (must be a valid email string) |
| `FIRST_ADMIN_PASSWORD` | Plaintext password; hashed by Argon2 before storage |
| `DATABASE_URL` | PostgreSQL async URL — read by `app.core.database` / `app.core.config` |

These variables should be set in your `.env` file at the project root (loaded by `docker compose`).

### How to run

```bash
# After migrations are applied and the API container is running:
docker compose exec api python -m app.scripts.seed_admin
```

**Example `.env` entries:**

```dotenv
FIRST_ADMIN_EMAIL=admin@yourcompany.com
FIRST_ADMIN_PASSWORD=SuperSecure1!
```

**Example output (first run):**

```
Admin user created: admin@yourcompany.com
```

**Example output (subsequent runs):**

```
Admin user already exists. Nothing to do.
```

### Script location

`/backend/app/scripts/seed_admin.py`

---

## Section 2: Billing Seed (`seed_billing`)

### What it does

`seed_billing` generates 90 days of synthetic `billing_records` for 11 resources across 6 resource groups under a single subscription (`mock-subscription-id`). It **clears** the entire `billing_records` table on each run and re-inserts fresh data. Use this script to load a clean, deterministic dataset for development and LLM recommendation testing.

Each resource follows one of four cost patterns designed to trigger specific recommendation categories:

| Pattern | Behaviour | Expected Recommendation |
|---------|-----------|------------------------|
| `flat` | Consistent daily cost ±5% noise, 7 days/week | Reserved Instance candidate |
| `dev_idle` | Same cost every day including weekends | Idle / auto-shutdown candidate |
| `workday` | Full cost Mon–Fri, 25% on weekends | Right-sizing / scheduling |
| `storage` | Very flat ±2% | Lifecycle management / deletion |

### Resources seeded

| Resource Name | Resource Group | Service | Pattern | ~Monthly Cost |
|---------------|---------------|---------|---------|--------------|
| `prod-vm-web-frontend` | `web-rg` | Virtual Machines | flat | $555 |
| `prod-vm-api-server` | `api-rg` | Virtual Machines | flat | $426 |
| `prod-sql-app-db` | `data-rg` | Azure SQL Database | flat | $660 |
| `prod-aks-data-cluster` | `data-rg` | Azure Kubernetes Service | flat | $930 |
| `prod-backup-archive` | `data-rg` | Azure Storage | storage | $144 |
| `prod-vm-batch-processor` | `batch-rg` | Virtual Machines | workday | $380 |
| `dev-vm-build-agent` | `dev-rg` | Virtual Machines | dev_idle | $192 |
| `dev-old-artifacts` | `dev-rg` | Azure Storage | storage | $75 |
| `dev-func-etl-processor` | `dev-rg` | Azure Functions | flat | $27 (below threshold) |
| `global-cdn-profile` | `shared-rg` | Azure CDN | flat | $105 |
| `prod-app-insights` | `shared-rg` | Azure Monitor | flat | $63 |

All records have `tag = ''` (no tenant association) and `currency = 'USD'`.

### How to run

```bash
docker compose exec api python -m app.scripts.seed_billing
```

**Example output:**

```
Cleared existing billing_records.
Inserted 990 billing records (11 resources × 90 days).

Resources seeded (approx monthly spend, sorted desc):
  $   930/mo  [flat     ]  prod-aks-data-cluster (data-rg)  ✓
  $   660/mo  [flat     ]  prod-sql-app-db (data-rg)  ✓
  ...
  $    27/mo  [flat     ]  dev-func-etl-processor (dev-rg)  ✗ (below $50 threshold)
```

---

## Section 3: Tenant Seed (`seed_tenants`)

### What it does

`seed_tenants` creates 6 fictional customer tenants and their associated billing records, tenant profiles, and attribution rows. Unlike `seed_billing`, it **does not clear** existing records — it upserts to be safe to re-run.

It performs four steps:

1. **Insert tenant-tagged billing records** — 90 days × 22 total resources across 6 tenants, each record with `tag = tenant_id`. Uses `ON CONFLICT DO NOTHING`.
2. **Upsert `TenantProfile` rows** — one per tenant, with `is_new = false` and the display name set.
3. **Seed prior-month attribution** — aggregates tagged billing records for `(year, month - 1)` and upserts `TenantAttribution` rows so the month-over-month delta field is populated for the current month.
4. **Run current-month attribution** — calls `run_attribution()` to compute the current month's `TenantAttribution` rows with MoM delta.

### Tenants seeded

| `tenant_id` | `display_name` | Subscription | ~Monthly Cost | Profile |
|-------------|---------------|-------------|--------------|---------|
| `tenant-acme` | Acme Corp | `sub-acme-0001` | ~$3,150 | Enterprise — heavy VMs, SQL, AKS |
| `tenant-stellar` | Stellar Labs | `sub-stellar-0002` | ~$1,720 | Startup — Kubernetes-heavy, weekday workloads |
| `tenant-nova` | Nova Digital | `sub-nova-0003` | ~$1,430 | Media — CDN and storage dominant |
| `tenant-apex` | Apex Retail | `sub-apex-0004` | ~$1,910 | Retail — always-on SQL, batch processing |
| `tenant-cerulean` | Cerulean Health | `sub-cerulean-0005` | ~$2,100 | Healthcare — compliance-heavy SQL and storage |
| `tenant-ironworks` | Ironworks Inc | `sub-ironworks-0006` | ~$930 | Manufacturing — batch processing, flat SQL |

### How to run

```bash
# Run AFTER seed_billing if you want both datasets:
docker compose exec api python -m app.scripts.seed_tenants
```

---

## Section 4: Test Fixture Reference

All fixtures are defined in `backend/tests/conftest.py`. The test suite uses `unittest.mock` throughout — **no real database is touched**. All DB interactions go through `AsyncMock` session objects.

### Infrastructure fixtures

| Fixture | Type | What it creates | Scope |
|---------|------|----------------|-------|
| `event_loop` | `asyncio.AbstractEventLoop` | Session-scoped event loop for all async tests | session |
| `mock_db_session` | `AsyncMock` | Mimics `AsyncSession`; pre-wires `commit`, `rollback`, `flush`, `refresh`, `add`, `execute`, `close` | function |
| `mock_redis` | `AsyncMock` | Mimics `redis.asyncio.Redis`; pre-wires `get`, `set`, `incr`, `expireat`, `delete` | function |
| `mock_azure_client` | `MagicMock` | Mimics Azure Cost Management fetch helper; `fetch_with_retry` returns `[]` | function |
| `async_client` | `httpx.AsyncClient` | Full ASGI test client with `get_db` and `get_current_user` dependency overrides; defaults to `test_user` | function |

### User fixtures

| Fixture | Creates | Key Values | Used In |
|---------|---------|------------|---------|
| `test_user` | `MagicMock` (User) | `email="viewer@example.com"`, `role="viewer"`, `is_active=True`, `failed_login_attempts=0` | `async_client`, `test_api_routes.py` |
| `admin_user` | `MagicMock` (User) | `email="admin@example.com"`, `role="admin"`, `is_active=True` | `test_api_routes.py` |
| `devops_user` | `MagicMock` (User) | `email="devops@example.com"`, `role="devops"`, `is_active=True` | Available; not directly used in current tests |

### Billing record fixtures

| Fixture | Creates | Key Values | Used In |
|---------|---------|------------|---------|
| `test_billing_records` | `list[MagicMock]` (6 BillingRecord) | 2 records per day for 3 days; alternates `service_name="Virtual Machines"` (tag=`tenant-a`) and `service_name="Storage"` (tag=`tenant-b`); `pre_tax_cost` ranges 200–220 and 50–60 | `test_ingestion_service.py` (implicitly), `test_attribution_service.py` (via inline helpers) |

### Anomaly fixtures

| Fixture | Creates | Key Values | Used In |
|---------|---------|------------|---------|
| `test_anomaly` | `MagicMock` (Anomaly) | `service_name="Virtual Machines"`, `resource_group="rg-prod"`, `severity="critical"`, `status="new"`, `pct_deviation=150.0`, `estimated_monthly_impact=1500.0`, `baseline_daily_avg=100.0`, `current_daily_cost=250.0` | `test_anomaly_service.py`, `test_api_routes.py` |

### Budget and notification fixtures

| Fixture | Creates | Key Values | Used In |
|---------|---------|------------|---------|
| `test_budget` | `MagicMock` (Budget) | `name="Monthly Subscription"`, `scope_type="subscription"`, `scope_value=None`, `amount_usd=10000.0`, `period="monthly"`, `is_active=True`, `start_date=first of current month` | `test_budget_service.py` |
| `test_threshold` | `MagicMock` (BudgetThreshold) | `threshold_percent=80`, `budget_id=test_budget.id`, `notification_channel_id=None`, `last_triggered_at=None`, `last_triggered_period=None` | `test_budget_service.py` |
| `test_channel_webhook` | `MagicMock` (NotificationChannel) | `channel_type="webhook"`, `config_json={"url": "https://hooks.example.com/test", "secret": "test-secret"}`, `is_active=True`, `owner_user_id=None` | `test_budget_service.py`, `test_notification_service.py` |
| `test_channel_email` | `MagicMock` (NotificationChannel) | `channel_type="email"`, `config_json={"address": "ops@example.com"}`, `is_active=True`, `owner_user_id=None` | `test_notification_service.py` |

### Factory functions (not fixtures — imported directly)

| Function | Signature | Purpose | Used In |
|----------|-----------|---------|---------|
| `make_scalars_result(items)` | `list → MagicMock` | Builds a mock `execute()` return whose `.scalars().all()` yields `items`; also sets `.scalar_one_or_none()`, `.scalar()`, `.all()`, `.first()` | All service test files |
| `make_scalar_result(value)` | `Any → MagicMock` | Builds a mock `execute()` return whose `.scalar()` yields a single value | All service test files |
| `make_access_token(user)` | `MagicMock → str` | Creates a real JWT access token for the mock user via `create_access_token` | `test_api_routes.py` |
| `_make_user(role, email, user_id)` | kwargs → `MagicMock` | Internal factory — call directly in test files to create variant users | `test_api_routes.py` |
| `_make_billing_record(**kwargs)` | kwargs → `MagicMock` | Internal factory — creates a single billing record with overridable defaults | `conftest.py` (builds `test_billing_records`) |
| `_make_anomaly(**kwargs)` | kwargs → `MagicMock` | Internal factory — creates an anomaly with overridable defaults | `test_anomaly_service.py`, `test_api_routes.py` |
| `_make_budget(**kwargs)` | kwargs → `MagicMock` | Internal factory — creates a budget with overridable defaults | `test_budget_service.py` |
| `_make_threshold(**kwargs)` | kwargs → `MagicMock` | Internal factory — creates a threshold with overridable defaults | `test_budget_service.py`, `test_notification_service.py` |
| `_make_notification_channel(**kwargs)` | kwargs → `MagicMock` | Internal factory — creates a channel with overridable defaults | `test_budget_service.py`, `test_notification_service.py` |

---

## Section 5: Sample Data Sets

Representative rows for each core table. These match what the seed scripts and test fixtures produce in practice.

### `users`

```
id                                   | email                      | full_name | role    | is_active | failed_login_attempts
-------------------------------------|----------------------------|-----------|---------|-----------|---------------------
<uuid>                               | admin@yourcompany.com      | Admin     | admin   | true      | 0
<uuid>                               | viewer@example.com         | Test Viewer | viewer | true     | 0
<uuid>                               | admin@example.com          | Test Admin  | admin  | true     | 0
<uuid>                               | devops@example.com         | Test Devops | devops | true    | 0
```

### `user_sessions`

```
id      | user_id | token_hash (SHA-256, 64 hex chars)                                | ip_address    | revoked
--------|---------|------------------------------------------------------------------|---------------|--------
<uuid>  | <uuid>  | a3f2c1d4e5b6...                                                  | 192.168.1.100 | false
```

### `billing_records` (sample — from `seed_billing`)

```
usage_date  | subscription_id        | resource_group | service_name        | meter_category | region  | tag | resource_name        | pre_tax_cost | currency
------------|------------------------|----------------|---------------------|----------------|---------|-----|----------------------|-------------|--------
2026-03-14  | mock-subscription-id   | web-rg         | Virtual Machines    | Compute        | eastus  |     | prod-vm-web-frontend | 18.432100   | USD
2026-03-14  | mock-subscription-id   | api-rg         | Virtual Machines    | Compute        | eastus  |     | prod-vm-api-server   | 14.085600   | USD
2026-03-14  | mock-subscription-id   | data-rg        | Azure SQL Database  | Databases      | eastus  |     | prod-sql-app-db      | 22.419800   | USD
2026-03-14  | mock-subscription-id   | data-rg        | Azure Kubernetes Service | Compute   | eastus  |     | prod-aks-data-cluster| 30.887200   | USD
2026-03-14  | mock-subscription-id   | batch-rg       | Virtual Machines    | Compute        | eastus  |     | prod-vm-batch-processor | 3.720000  | USD  ← weekend: 25% of 16.00
2026-03-14  | mock-subscription-id   | dev-rg         | Virtual Machines    | Compute        | westus2 |     | dev-vm-build-agent   | 6.382400   | USD
```

### `billing_records` (sample — from `seed_tenants`)

```
usage_date  | subscription_id    | resource_group   | service_name        | tag           | resource_name       | pre_tax_cost
------------|--------------------|------------------|---------------------|---------------|---------------------|-------------
2026-03-14  | sub-acme-0001      | acme-prod-rg     | Virtual Machines    | tenant-acme   | acme-app-server-01  | 21.834000
2026-03-14  | sub-acme-0001      | acme-prod-rg     | Azure SQL Database  | tenant-acme   | acme-prod-db        | 28.112000
2026-03-14  | sub-stellar-0002   | stellar-compute-rg | Azure Kubernetes Service | tenant-stellar | stellar-k8s     | 7.920000  ← weekend
2026-03-14  | sub-nova-0003      | nova-cdn-rg      | Azure CDN           | tenant-nova   | nova-media-cdn      | 13.762000
2026-03-14  | sub-cerulean-0005  | cerulean-hipaa-rg | Azure SQL Database | tenant-cerulean | cerulean-patient-db | 37.940000
```

### `tenant_profiles`

```
id      | tenant_id          | display_name     | is_new | first_seen
--------|--------------------|--------------------|--------|------------
<uuid>  | tenant-acme        | Acme Corp          | false  | 2025-12-14
<uuid>  | tenant-stellar     | Stellar Labs        | false  | 2025-12-14
<uuid>  | tenant-nova        | Nova Digital        | false  | 2025-12-14
<uuid>  | tenant-apex        | Apex Retail         | false  | 2025-12-14
<uuid>  | tenant-cerulean    | Cerulean Health     | false  | 2025-12-14
<uuid>  | tenant-ironworks   | Ironworks Inc       | false  | 2025-12-14
```

### `tenant_attributions` (after `seed_tenants`)

```
tenant_id          | year | month | total_cost   | pct_of_total | mom_delta_usd | top_service_category
-------------------|------|-------|--------------|-------------|---------------|---------------------
tenant-acme        | 2026 | 3     | 2890.400000  | 26.2104      | 0.000000      | Virtual Machines
tenant-stellar     | 2026 | 3     | 1621.800000  | 14.7012      | 0.000000      | Azure Kubernetes Service
tenant-nova        | 2026 | 3     | 1374.300000  | 12.4567      | 0.000000      | Azure Storage
tenant-apex        | 2026 | 3     | 1795.200000  | 16.2701      | 0.000000      | Azure SQL Database
tenant-cerulean    | 2026 | 3     | 2097.600000  | 19.0140      | 0.000000      | Azure SQL Database
tenant-ironworks   | 2026 | 3     | 870.300000   | 7.8876       | 0.000000      | Virtual Machines
```

(Values are approximations; exact figures vary due to random noise in `_daily_cost()`.)

### `anomalies` (typical test fixture values)

```
id      | detected_date | service_name    | resource_group | severity | status | pct_deviation | estimated_monthly_impact
--------|---------------|-----------------|----------------|----------|--------|--------------|------------------------
<uuid>  | today         | Virtual Machines | rg-prod       | critical | new    | 150.00       | 1500.00
```

### `budgets` (typical test fixture values)

```
id      | name                  | scope_type   | scope_value | amount_usd | period  | is_active | start_date
--------|-----------------------|--------------|-------------|------------|---------|-----------|------------
<uuid>  | Monthly Subscription  | subscription | NULL        | 10000.00   | monthly | true      | 2026-03-01
```

### `budget_thresholds` (typical test fixture values)

```
id      | budget_id | threshold_percent | notification_channel_id | last_triggered_period
--------|-----------|-------------------|-------------------------|---------------------
<uuid>  | <uuid>    | 80                | NULL                    | NULL
```

### `notification_channels` (typical test fixture values)

```
id      | name             | channel_type | config_json                                           | is_active
--------|------------------|--------------|-------------------------------------------------------|----------
<uuid>  | Test webhook     | webhook      | {"url": "https://hooks.example.com/test", "secret": "test-secret"} | true
<uuid>  | Test email       | email        | {"address": "ops@example.com"}                        | true
```

### `ingestion_runs` (sample)

```
id      | started_at              | completed_at            | status  | triggered_by | records_ingested | window_start           | window_end
--------|-------------------------|-------------------------|---------|--------------|-----------------|------------------------|------------------------
<uuid>  | 2026-03-14T06:00:00Z    | 2026-03-14T06:00:08Z    | success | scheduler    | 42               | 2026-03-13T06:00:00Z   | 2026-03-14T06:00:00Z
```

---

## Section 6: Running the Full Dev Stack with Data

### Prerequisites

- Docker Desktop running
- `.env` file at project root with at minimum:

```dotenv
FIRST_ADMIN_EMAIL=admin@example.com
FIRST_ADMIN_PASSWORD=AdminPassword1!
DATABASE_URL=postgresql+asyncpg://cloudcost:cloudcost@db:5432/cloudcost
REDIS_URL=redis://redis:6379/0
JWT_SECRET_KEY=change-me-in-production-min-32-chars
```

### Step 1: Start Docker Compose

```bash
docker compose up -d
```

This starts:
- `db` — PostgreSQL 16
- `redis` — Redis 7
- `api` — FastAPI backend (uvicorn)
- `frontend` — Next.js frontend (if included in compose file)

Wait for the API container to pass its health check:

```bash
docker compose ps          # check STATUS = "healthy" or "running"
docker compose logs api    # watch for "Application startup complete."
```

### Step 2: Run database migrations

```bash
docker compose exec api alembic upgrade head
```

Expected output ends with:
```
Running upgrade 29e392128bad -> c8f1a9b3d2e4, add_budget_and_notification_tables
```

### Step 3: Seed the admin user

```bash
docker compose exec api python -m app.scripts.seed_admin
```

Expected output:
```
Admin user created: admin@example.com
```

### Step 4: (Optional) Load demo billing data

Load the plain billing dataset (no tenant tagging — good for testing anomaly detection and recommendations):

```bash
docker compose exec api python -m app.scripts.seed_billing
```

Or load the multi-tenant dataset (includes tenant profiles and attribution rows — good for testing the attribution dashboard):

```bash
docker compose exec api python -m app.scripts.seed_tenants
```

You can run both. `seed_tenants` does not clear existing `billing_records` rows, so it appends tenant-tagged records to the plain records inserted by `seed_billing`.

### Step 5: Verify expected state

After all steps, the database should contain:

| Table | Expected rows |
|-------|--------------|
| `users` | 1 (the admin) |
| `user_sessions` | 0 (populated on first login) |
| `billing_records` | 990 (plain, from `seed_billing`) + 1,980 (tenant-tagged, from `seed_tenants`) = 2,970 if both run |
| `tenant_profiles` | 6 (from `seed_tenants`) |
| `tenant_attributions` | 12 (6 tenants × 2 months: prior + current) |
| `ingestion_runs` | 0 (populated by actual ingestion or manual trigger) |
| `anomalies` | 0 (populated by the anomaly detection scheduler) |
| `recommendations` | 0 (populated by the LLM recommendation scheduler) |
| `budgets` | 0 (populated via API) |
| `notification_channels` | 0 (populated via API) |

### Step 6: Log in

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=admin@example.com&password=AdminPassword1!" \
  | python -m json.tool
```

A successful response contains `access_token`, `token_type: "bearer"`, and `expires_in`.

### Resetting to a clean state

```bash
# Tear down containers and volumes (destroys all data):
docker compose down -v

# Start fresh:
docker compose up -d
# Then re-run Steps 2–4
```

---

## Section 7: Running the Test Suite

The test suite requires no live services — all external dependencies are mocked.

```bash
# From the backend directory, or via docker:
docker compose exec api pytest backend/tests/ -v
```

Or if running locally with a virtual environment:

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

**Test files and what they cover:**

| File | Coverage |
|------|---------|
| `test_security.py` | JWT creation/decode, password hashing, `hash_token` |
| `test_ingestion_service.py` | `_parse_usage_date`, `_map_record`, delta window, upsert, run lifecycle |
| `test_anomaly_service.py` | Detection algorithm, severity classification, CRUD helpers |
| `test_attribution_service.py` | `apply_allocation_rule` (all methods), tenant/rule CRUD |
| `test_budget_service.py` | Budget/threshold CRUD, period helpers, `_check_one_budget` |
| `test_notification_service.py` | Webhook/email sending, delivery logging, retry logic |
| `test_api_routes.py` | Auth endpoints, RBAC, anomaly routes, ingestion status |

All tests are fully isolated: no shared state between test functions. The `event_loop` fixture is session-scoped, which is the only cross-test dependency.
