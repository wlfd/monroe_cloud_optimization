# CloudCost

Azure infrastructure cost optimization for Fileread. AI-powered recommendations, anomaly detection, and per-tenant cost attribution.

## Quick Start (Local Development)

### Prerequisites
- Docker Desktop
- Node.js 20+ (for frontend development without Docker)
- Python 3.12+ (for backend development without Docker)

### 1. Configure environment
```bash
cp .env.example .env.local
# Edit .env.local: set JWT_SECRET_KEY to a random 64-byte hex string
# Generate one with: openssl rand -hex 64
```

### 2. Start services
```bash
docker compose up -d
```

This starts PostgreSQL, Redis, runs Alembic migrations, and starts the API and frontend.

### 3. Create the first admin user
```bash
FIRST_ADMIN_EMAIL=admin@example.com \
FIRST_ADMIN_PASSWORD=YourStrongPassword \
  docker compose exec api python -m app.scripts.seed_admin
```

### 4. Access the application
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/api/docs |
| API (ReDoc) | http://localhost:8000/api/redoc |

## Development

### Backend
```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
# Run with auto-reload:
DATABASE_URL=postgresql+asyncpg://cloudcost:localdev@localhost:5432/cloudcost \
  uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev   # Starts at http://localhost:3000
```

### Migrations
```bash
cd backend
# Create a new migration after model changes:
alembic revision --autogenerate -m "describe the change"
# Apply:
alembic upgrade head
# Rollback one step:
alembic downgrade -1
```

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system design.

**Stack:** FastAPI + PostgreSQL (async SQLAlchemy 2.0) + React + shadcn/ui + Docker
**Auth:** JWT access tokens (1h) + HttpOnly refresh token cookie (7d)
**Deployment target:** Azure Container Apps (API) + Azure Static Web Apps (frontend)
