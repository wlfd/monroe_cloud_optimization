.PHONY: lint format test \
        lint-backend format-backend test-backend \
        lint-frontend format-frontend test-frontend \
        build-tools

TOOLS = docker compose -f docker-compose.tools.yml

# ── Build tool images ─────────────────────────────────────────────────────────
build-tools:
	$(TOOLS) build

# ── Backend ───────────────────────────────────────────────────────────────────
lint-backend:
	$(TOOLS) run --rm backend-tools ruff check app/ tests/ migrations/

lint-backend-fix:
	$(TOOLS) run --rm backend-tools ruff check --fix app/ tests/ migrations/

format-backend:
	$(TOOLS) run --rm backend-tools ruff format app/ tests/ migrations/

format-backend-check:
	$(TOOLS) run --rm backend-tools ruff format --check app/ tests/ migrations/

test-backend:
	$(TOOLS) run --rm backend-tools pytest tests/ -v

test-backend-coverage:
	$(TOOLS) run --rm backend-tools pytest tests/ -v --cov=app --cov-report=html --cov-report=term

# ── Frontend ──────────────────────────────────────────────────────────────────
lint-frontend:
	$(TOOLS) run --rm frontend-tools npm run lint

lint-frontend-fix:
	$(TOOLS) run --rm frontend-tools npm run lint:fix

format-frontend:
	$(TOOLS) run --rm frontend-tools npm run format

format-frontend-check:
	$(TOOLS) run --rm frontend-tools npm run format:check

test-frontend:
	$(TOOLS) run --rm frontend-tools npm test

test-frontend-coverage:
	$(TOOLS) run --rm frontend-tools npm run test:coverage

# ── Combined ──────────────────────────────────────────────────────────────────
lint: lint-backend lint-frontend

lint-fix: lint-backend-fix lint-frontend-fix

format: format-backend format-frontend

test: test-backend test-frontend

# ── Dev environment ───────────────────────────────────────────────────────────
up:
	docker compose up --build

up-detached:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose run --rm migrate

seed:
	docker compose exec api python -m app.scripts.seed_admin
