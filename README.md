# CloudCost

Azure cloud cost optimization SaaS platform. CloudCost ingests Azure billing data, detects spending anomalies, generates AI-powered recommendations, and provides per-tenant cost attribution — all in a single hosted application.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Prerequisites](#3-prerequisites)
4. [Quick Start — Docker Compose](#4-quick-start--docker-compose)
5. [Manual Local Setup](#5-manual-local-setup)
6. [Environment Variables Reference](#6-environment-variables-reference)
7. [Database Setup](#7-database-setup)
8. [Seeding Test Data](#8-seeding-test-data)
9. [Running Tests](#9-running-tests)
10. [API Documentation](#10-api-documentation)
11. [Development Workflow](#11-development-workflow)
12. [User Roles](#12-user-roles)
13. [Project Structure](#13-project-structure)
14. [Troubleshooting](#14-troubleshooting)
15. [Contributing](#15-contributing)

---

## 1. Project Overview

CloudCost is a multi-tenant SaaS application that helps engineering and finance teams understand and reduce their Azure cloud spending.

### Key Features

- **Cost Ingestion** — Pulls Azure Cost Management data on a 4-hour schedule via APScheduler. Supports a mock mode for local development without real Azure credentials.
- **Anomaly Detection** — Identifies unexpected cost spikes across subscriptions and resource groups, with configurable sensitivity.
- **AI Recommendations** — Uses Claude (Anthropic) or Azure OpenAI to generate actionable cost-saving recommendations daily at 02:00 UTC, qualified by a configurable monthly spend threshold.
- **Tenant Attribution** — Allocates cloud spend to internal tenants or teams using tagging rules, enabling accurate chargeback and showback reporting.
- **Budgets & Alerts** — Define per-tenant or per-subscription budgets with threshold alerts delivered via email or webhook.
- **Notifications** — Flexible notification delivery with automatic retry for failed webhook deliveries (every 15 minutes).

### Screenshots

> _Screenshots coming soon. Run the app locally and visit http://localhost:3000._

---

## 2. Architecture Overview

```
                          ┌─────────────────────────────────────┐
                          │           Browser / Client           │
                          │  React 19 + Vite + shadcn/ui         │
                          │  TanStack Query · Recharts           │
                          └──────────────────┬──────────────────┘
                                             │ HTTP (JSON + JWT)
                          ┌──────────────────▼──────────────────┐
                          │            FastAPI (Python 3.12)     │
                          │  /api/v1/*  ·  Async SQLAlchemy 2.0  │
                          │  APScheduler (ingestion · AI · alerts│
                          └────────┬──────────────┬─────────────┘
                                   │              │
              ┌────────────────────▼──┐  ┌────────▼────────────┐
              │   PostgreSQL 15       │  │   Redis 7            │
              │   (primary store)     │  │   (job dedup /       │
              └───────────────────────┘  │    recommendation    │
                                         │    cache)            │
                                         └─────────────────────┘
                                                   │
                          ┌────────────────────────▼────────────┐
                          │          Azure Cost Management API   │
                          │          (or MOCK_AZURE=true)        │
                          └─────────────────────────────────────┘
```

**Component summary:**

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4, shadcn/ui | SPA served by Vite dev server (Docker) or Nginx (production) |
| Backend API | FastAPI, Python 3.12, SQLAlchemy 2.0 (async) | REST API, business logic, scheduled jobs |
| Database | PostgreSQL 15 | Persistent storage for all domain data |
| Cache / Queue | Redis 7 | Recommendation result cache, job deduplication |
| Scheduler | APScheduler 3.11 | In-process cron/interval jobs (ingestion, AI, budget checks, webhook retry) |
| AI Layer | Anthropic Claude / Azure OpenAI | Daily cost recommendation generation |
| Azure Client | azure-mgmt-costmanagement, azure-identity | Live billing data ingestion |

---

## 3. Prerequisites

### Docker path (recommended)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 4.x+ (includes Docker Compose v2)

That's it. Everything else runs inside containers.

### Manual path

- Python 3.12+
- Node.js 20+
- PostgreSQL 15+
- Redis 7+

### Azure credentials (for live data)

- Azure subscription with Cost Management Reader role assigned to a service principal
- `AZURE_SUBSCRIPTION_ID`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`

If you don't have Azure credentials, set `MOCK_AZURE=true` in your `.env` file. The ingestion service will generate synthetic cost data instead.

---

## 4. Quick Start — Docker Compose

This is the fastest way to get a fully working local environment.

### Step 1: Clone the repository

```bash
git clone <repo-url> monroe_cloud_optimization
cd monroe_cloud_optimization
```

### Step 2: Configure environment

```bash
cp .env.example .env.local
```

Open `.env.local` and set at minimum:

```bash
# Generate a secure secret:  openssl rand -hex 64
JWT_SECRET_KEY=<your-64-byte-hex-string>

# Bootstrap admin account (used by the seed script below)
FIRST_ADMIN_EMAIL=admin@yourdomain.com
FIRST_ADMIN_PASSWORD=<strong-password>
```

For live Azure data, also fill in the `AZURE_*` variables. Otherwise leave `MOCK_AZURE=false` (the default) or set it to `true`.

### Step 3: Build and start all services

```bash
docker compose up --build
```

Docker Compose will:
1. Start PostgreSQL 15 and Redis 7
2. Run Alembic migrations (`alembic upgrade head`) via the `migrate` service
3. Start the FastAPI backend on port 8000
4. Start the React frontend dev server on port 3000

### Step 4: Seed the first admin user

In a separate terminal, after the `api` service is healthy:

```bash
FIRST_ADMIN_EMAIL=admin@yourdomain.com \
FIRST_ADMIN_PASSWORD=YourStrongPassword \
  docker compose exec api python -m app.scripts.seed_admin
```

### Step 5: Access the application

| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API — Swagger UI | http://localhost:8000/api/docs |
| API — ReDoc | http://localhost:8000/api/redoc |

Log in at the frontend with the credentials you used in Step 4.

### Stopping the stack

```bash
docker compose down          # Stop containers, keep database volume
docker compose down -v       # Stop containers AND delete database volume
```

---

## 5. Manual Local Setup

Use this path when you need IDE debugging, faster hot-reload, or want to run only part of the stack in Docker.

You still need PostgreSQL and Redis running. The easiest approach is to start only those services:

```bash
docker compose up db redis
```

### Backend

```bash
cd backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# Configure environment (backend reads from backend/.env)
cp ../.env.example .env
# Edit .env — set DATABASE_URL, REDIS_URL, JWT_SECRET_KEY at minimum

# Run database migrations
alembic upgrade head

# Start the API with auto-reload
uvicorn app.main:app --reload --port 8000
```

The API is available at http://localhost:8000.

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure the API base URL
# Create frontend/.env.local:
echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env.local

# Start the dev server (port 3000)
npm run dev
```

The frontend is available at http://localhost:3000.

---

## 6. Environment Variables Reference

Copy `.env.example` to `.env.local` (Docker path) or `backend/.env` (manual path). The backend reads variables from `backend/.env` or the process environment; the frontend reads `VITE_*` variables at build time.

### Core

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `APP_ENV` | No | `development` | Runtime environment (`development` \| `production`) |
| `DEBUG` | No | `false` | Enable debug logging |

### Database

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://cloudcost:localdev@localhost:5432/cloudcost` | Async PostgreSQL connection string. Must use `asyncpg` driver. |

### Redis

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `REDIS_URL` | Yes | `redis://localhost:6379/0` | Redis connection URL |

### Authentication

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | **Yes** | `change-me-in-production` | Secret used to sign JWTs. Generate with `openssl rand -hex 64`. Never commit a real value. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | No | `60` | Access token lifetime in minutes |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | No | `7` | Refresh token lifetime in days |

### CORS

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CORS_ORIGINS` | No | `["http://localhost:3000"]` | JSON array of allowed origins |

### Admin Bootstrap

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIRST_ADMIN_EMAIL` | For seed script | — | Email address for the initial admin user |
| `FIRST_ADMIN_PASSWORD` | For seed script | — | Password for the initial admin user |

### Azure Cost Management

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_SUBSCRIPTION_ID` | For live data | — | Azure subscription UUID |
| `AZURE_CLIENT_ID` | For live data | — | Service principal application (client) ID |
| `AZURE_TENANT_ID` | For live data | — | Azure AD tenant ID |
| `AZURE_CLIENT_SECRET` | For live data | — | Service principal client secret |
| `AZURE_SUBSCRIPTION_SCOPE` | No | — | Override scope path. Computed automatically from `AZURE_SUBSCRIPTION_ID` if blank. |
| `MOCK_AZURE` | No | `false` | Set `true` to use synthetic cost data instead of live Azure API |

### AI / LLM Recommendations

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | For AI features | — | Anthropic API key for Claude |
| `ANTHROPIC_MODEL` | No | `claude-sonnet-4-6` | Claude model ID to use |
| `AZURE_OPENAI_ENDPOINT` | For Azure OpenAI | — | e.g. `https://{resource}.openai.azure.com/` |
| `AZURE_OPENAI_API_KEY` | For Azure OpenAI | — | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | No | `gpt-4o` | Azure OpenAI deployment name |
| `LLM_DAILY_CALL_LIMIT` | No | `100` | Maximum AI recommendation API calls per day |
| `LLM_MIN_MONTHLY_SPEND_THRESHOLD` | No | `50.0` | Minimum monthly spend (USD) to qualify a resource for AI analysis |

### SMTP / Email Notifications

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SMTP_HOST` | For email alerts | — | SMTP server hostname (compatible with SendGrid, SES, Azure Communication Services) |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | For email alerts | — | SMTP authentication username |
| `SMTP_PASSWORD` | For email alerts | — | SMTP authentication password |
| `SMTP_FROM` | No | `noreply@cloudcost.local` | Sender address for outgoing emails |
| `SMTP_START_TLS` | No | `true` | Use STARTTLS for SMTP connections |

### Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE_URL` | Yes | `http://localhost:8000/api/v1` | Backend API base URL, injected at Vite build time |

---

## 7. Database Setup

CloudCost uses [Alembic](https://alembic.sqlalchemy.org/) for schema migrations. The Docker Compose `migrate` service runs migrations automatically on startup.

### Apply all migrations (bring schema to latest)

```bash
cd backend
alembic upgrade head
```

### Create a new migration after changing models

```bash
cd backend
alembic revision --autogenerate -m "add resource_tags column to billing_records"
# Review the generated file in backend/migrations/versions/
alembic upgrade head
```

Always review auto-generated migration files before applying — Alembic may miss complex changes like renamed columns.

### Roll back one migration

```bash
cd backend
alembic downgrade -1
```

### Roll back to a specific revision

```bash
cd backend
alembic downgrade <revision-id>
```

---

## 8. Seeding Test Data

### Admin user

The seed script creates the first admin user using `FIRST_ADMIN_EMAIL` and `FIRST_ADMIN_PASSWORD`. It is idempotent — running it multiple times will not create duplicate users.

**Docker:**

```bash
FIRST_ADMIN_EMAIL=admin@example.com \
FIRST_ADMIN_PASSWORD=YourStrongPassword \
  docker compose exec api python -m app.scripts.seed_admin
```

**Manual (with virtual environment activated):**

```bash
cd backend
FIRST_ADMIN_EMAIL=admin@example.com \
FIRST_ADMIN_PASSWORD=YourStrongPassword \
  python -m app.scripts.seed_admin
```

### Mock Azure data

Set `MOCK_AZURE=true` in your `.env` file, then trigger an ingestion run manually via the API or wait for the 4-hour scheduled job. The mock client generates realistic synthetic cost records across multiple resource groups.

---

## 9. Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=app --cov-report=html

# Open the HTML coverage report
open htmlcov/index.html    # macOS
xdg-open htmlcov/index.html  # Linux
```

Test dependencies (`pytest`, `pytest-asyncio`, `httpx`, `anyio`) are in `requirements-dev.txt`.

### Frontend

```bash
cd frontend

# Run tests (Vitest + Testing Library)
npm test

# Run tests with coverage
npm run test:coverage
```

Frontend tests use [Vitest](https://vitest.dev/), [Testing Library](https://testing-library.com/), and [MSW](https://mswjs.io/) for API mocking.

---

## 10. API Documentation

The FastAPI backend generates interactive documentation automatically.

| Interface | URL | Notes |
|-----------|-----|-------|
| Swagger UI | http://localhost:8000/api/docs | Interactive — click "Authorize" to paste a JWT Bearer token |
| ReDoc | http://localhost:8000/api/redoc | Read-only, better for browsing schemas |

### Key endpoint groups

All routes are prefixed with `/api/v1`.

| Tag | Prefix | Description |
|-----|--------|-------------|
| `auth` | `/api/v1/auth` | Login, logout, token refresh, current user profile |
| `ingestion` | `/api/v1/ingestion` | Trigger manual ingestion runs, view run history |
| `cost` | `/api/v1/cost` | Query cost data, breakdowns by resource/date |
| `anomalies` | `/api/v1/anomalies` | List and acknowledge detected cost anomalies |
| `recommendations` | `/api/v1/recommendations` | AI-generated cost-saving recommendations |
| `attribution` | `/api/v1/attribution` | Tenant cost attribution rules and reports |
| `budgets` | `/api/v1/budgets` | Budget definitions and threshold configuration |
| `notifications` | `/api/v1/notifications` | Notification channels and delivery history |
| `settings` | `/api/v1/settings` | Application and user settings |
| `health` | `/api/v1/health` | Liveness probe (`GET /api/v1/health`) |

### Authentication

All non-public endpoints require a `Bearer` token in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtain a token via `POST /api/v1/auth/login`. Access tokens expire after 60 minutes (default). Use `POST /api/v1/auth/refresh` with the HttpOnly refresh token cookie to obtain a new access token without re-entering credentials.

---

## 11. Development Workflow

### Backend code style

CloudCost uses [Ruff](https://docs.astral.sh/ruff/) for both formatting and linting.

```bash
cd backend

# Format code
ruff format .

# Lint (check only)
ruff check .

# Lint and auto-fix safe issues
ruff check . --fix
```

### Frontend code style

```bash
cd frontend

# Lint with ESLint
npm run lint
```

TypeScript is enforced via `tsc` — the build step (`npm run build`) will fail on type errors.

### Adding a new API route

1. Create `backend/app/api/v1/<feature>.py` with a `router = APIRouter(...)`.
2. Create `backend/app/schemas/<feature>.py` for Pydantic request/response models.
3. Add service logic to `backend/app/services/<feature>.py`.
4. Register the router in `backend/app/api/v1/router.py`:

```python
from app.api.v1 import my_feature as my_feature_module

api_router.include_router(
    my_feature_module.router,
    prefix="/my-feature",
    tags=["my-feature"],
)
```

5. If the feature requires new database tables, create a model in `backend/app/models/<feature>.py`, import it in `backend/app/models/__init__.py`, and generate a migration:

```bash
cd backend
alembic revision --autogenerate -m "add my_feature table"
alembic upgrade head
```

---

## 12. User Roles

CloudCost uses four fixed roles assigned per user. Role is embedded in the JWT and checked on protected endpoints.

| Role | Who it's for | Permissions |
|------|-------------|-------------|
| `admin` | Platform administrators | Full access: manage users, view all data, configure system settings, trigger ingestion, manage budgets and notifications |
| `devops` | Engineering / infrastructure teams | View all cost data, anomalies, recommendations, and attribution; trigger manual ingestion runs; acknowledge anomalies |
| `finance` | Finance and billing teams | View all cost data, budgets, attribution reports, and recommendations; manage budget thresholds; export reports |
| `viewer` | Read-only stakeholders | View cost dashboards, anomalies, and recommendations; no write access |

Users are created by an `admin` via the settings API or the admin UI. Roles cannot be self-assigned.

---

## 13. Project Structure

```
monroe_cloud_optimization/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── auth.py           # Login, logout, token refresh
│   │   │       ├── ingestion.py      # Manual ingestion trigger + run history
│   │   │       ├── cost.py           # Cost query endpoints
│   │   │       ├── anomaly.py        # Anomaly list + acknowledgement
│   │   │       ├── recommendation.py # AI recommendation endpoints
│   │   │       ├── attribution.py    # Tenant attribution rules + reports
│   │   │       ├── budget.py         # Budget CRUD + threshold config
│   │   │       ├── notification.py   # Notification channels + history
│   │   │       ├── settings.py       # App and user settings
│   │   │       ├── health.py         # Health probe
│   │   │       └── router.py         # Registers all routers
│   │   ├── core/
│   │   │   ├── config.py             # Pydantic Settings (env var loading)
│   │   │   ├── database.py           # Async SQLAlchemy engine + session
│   │   │   ├── dependencies.py       # FastAPI dependency injection (get_db, auth)
│   │   │   ├── scheduler.py          # APScheduler instance
│   │   │   └── security.py           # JWT creation/verification, password hashing
│   │   ├── models/
│   │   │   ├── user.py               # User + UserSession (auth)
│   │   │   ├── billing.py            # Ingestion runs + cost records
│   │   │   ├── recommendation.py     # AI recommendation records
│   │   │   ├── attribution.py        # Tenant attribution rules + allocations
│   │   │   ├── budget.py             # Budget definitions + events
│   │   │   └── notification.py       # Notification channels + delivery log
│   │   ├── schemas/                  # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── azure_client.py       # Azure Cost Management API wrapper (+ mock)
│   │   │   ├── ingestion.py          # Ingestion orchestration + stale run recovery
│   │   │   ├── cost.py               # Cost aggregation queries
│   │   │   ├── anomaly.py            # Anomaly detection logic
│   │   │   ├── recommendation.py     # AI recommendation generation + daily job
│   │   │   ├── attribution.py        # Cost attribution engine
│   │   │   ├── budget.py             # Budget threshold checks
│   │   │   └── notification.py       # Notification delivery + webhook retry
│   │   ├── templates/                # Email templates
│   │   └── main.py                   # FastAPI app factory, lifespan, middleware
│   ├── migrations/
│   │   ├── versions/                 # Alembic migration scripts
│   │   └── env.py                    # Alembic environment config
│   ├── tests/                        # pytest test suite
│   ├── Dockerfile
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/
│   ├── src/
│   │   ├── components/               # Shared UI components (shadcn/ui based)
│   │   ├── pages/                    # Route-level page components
│   │   ├── hooks/                    # Custom React hooks
│   │   ├── api/                      # Axios client + TanStack Query hooks
│   │   └── main.tsx                  # App entry point
│   ├── Dockerfile
│   └── package.json
├── .env.example                      # Environment variable template
├── docker-compose.yml                # Local development stack
└── README.md
```

---

## 14. Troubleshooting

### PostgreSQL connection errors

**Symptom:** `asyncpg.exceptions.ConnectionRefusedError` or `could not connect to server`

- Verify PostgreSQL is running: `docker compose ps db`
- Check that `DATABASE_URL` uses `postgresql+asyncpg://` (not `postgresql://`)
- For manual setup, confirm PostgreSQL is listening on the configured host/port
- Check that the database and user exist: `psql -U cloudcost -d cloudcost -h localhost`

### Redis connection errors

**Symptom:** `redis.exceptions.ConnectionError`

- Verify Redis is running: `docker compose ps redis`
- Check `REDIS_URL` in your `.env` file
- For manual setup, confirm Redis is running: `redis-cli ping` should return `PONG`

### Migration failures

**Symptom:** `alembic upgrade head` fails or `migrate` container exits with an error

- Check that `DATABASE_URL` is correct and the database is accessible
- If you see `Target database is not up to date`, run `alembic upgrade head` again
- If migration scripts have conflicts, check `backend/migrations/versions/` for multiple heads: `alembic heads`
- To start fresh in development (destructive): `docker compose down -v && docker compose up --build`

### Azure credential errors

**Symptom:** `ClientAuthenticationError` or `azure.core.exceptions.HttpResponseError`

- Confirm all four `AZURE_*` variables are set and correct
- Verify the service principal has the `Cost Management Reader` role on the target subscription
- For local development without Azure access, set `MOCK_AZURE=true`

### JWT secret not set

**Symptom:** All logins fail with 500 errors, or tokens are rejected immediately

- Ensure `JWT_SECRET_KEY` is set to a non-default value in your `.env` file
- Generate a new secret: `openssl rand -hex 64`
- Restart the API after changing the secret (all existing tokens will be invalidated)

### Port conflicts

**Symptom:** `Bind for 0.0.0.0:5432 failed: port is already allocated`

- A local PostgreSQL or Redis instance is using the port
- Either stop the local service, or change the host port mapping in `docker-compose.yml` (e.g., `"5433:5432"`) and update `DATABASE_URL` accordingly

### Frontend cannot reach the API

**Symptom:** Network errors or CORS errors in the browser console

- Confirm `VITE_API_BASE_URL` is set to `http://localhost:8000/api/v1`
- Confirm the `api` container is healthy: `docker compose ps`
- Check that `CORS_ORIGINS` in the backend includes `http://localhost:3000`

---

## 15. Contributing

### Branching

- Branch from `main` for all changes
- Use descriptive branch names: `feat/budget-alerts`, `fix/ingestion-stale-runs`, `chore/update-deps`

### Commit style

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(budget): add percentage-based threshold alerts
fix(ingestion): recover stale runs on startup
chore(deps): upgrade FastAPI to 0.115
```

### Pull requests

1. Ensure all tests pass locally before opening a PR
2. Include a short description of what changed and why
3. Link any related issues
4. Keep PRs focused — one logical change per PR

### Code standards

- Backend: `ruff format .` and `ruff check .` must pass with no errors
- Frontend: `npm run lint` must pass with no errors; no TypeScript errors (`npm run build`)
- New service logic should have corresponding tests in `backend/tests/`

### Local environment checklist

- [ ] `docker compose up --build` runs without errors
- [ ] Frontend loads at http://localhost:3000
- [ ] Login works with seeded admin credentials
- [ ] `pytest tests/ -v` passes
- [ ] `npm test` passes
