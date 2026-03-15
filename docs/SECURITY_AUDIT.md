# Public Repository Security Audit

## Date

2026-03-14

## Summary

PASS — No real credentials exist in any tracked or trackable source file. One real Anthropic API key was found in `.env.local`, which is already covered by `.gitignore` (`*.local` pattern). All gaps in `.env.example` and `.gitignore` have been remediated in this audit.

---

## Findings

### Critical (blocks public upload)

None.

### Fixed in This Audit

**1. `.env.example` was missing the majority of `config.py` Settings fields**

- `config.py` defines 27 environment variables across 6 groups (Core, Database, Redis, Security, Azure, AI/LLM, SMTP).
- The old `.env.example` covered only 9 of them (Database, Redis, JWT, CORS, Admin Bootstrap, APP_ENV, DEBUG, and VITE_API_BASE_URL).
- Missing groups: all `AZURE_*` variables, all `ANTHROPIC_*` / `AZURE_OPENAI_*` variables, all `LLM_*` variables, all `SMTP_*` variables, and `MOCK_AZURE`.
- **Fix:** Rewrote `.env.example` to include all 27 fields with safe placeholder values, inline documentation, and correct field names (e.g., `SMTP_USER` not `SMTP_USERNAME`; `SMTP_FROM` not `SMTP_FROM_ADDRESS`; `SMTP_START_TLS` not `SMTP_TLS`).

**2. `frontend/.env.example` had no documentation header**

- File existed with one line (`VITE_API_BASE_URL=...`) and no comments.
- **Fix:** Added a comment header explaining purpose, copy instructions, and variable description.

**3. `.gitignore` was missing four patterns from the recommended baseline**

- Missing: `frontend/dist/`, `frontend/.vite/`, `*.cover`, `Thumbs.db`.
- **Fix:** Added all four patterns in the appropriate sections.

**4. Real Anthropic API key present in `.env.local`**

- `.env.local` contained a live Anthropic API key (`sk-ant-api03-YpxkaqedDyfT3bMtPcej7KtljX2i3LAixvnqgCa3-...`).
- This file is already excluded from git by the `*.local` pattern in `.gitignore`, so the key was never committed and is not at risk of being pushed.
- **Recommended action (manual):** Rotate this API key at https://console.anthropic.com and replace the value in `.env.local` with the new key. Treat the exposed key as compromised since it may have been visible in shell history, logs, or editor sessions.

### Accepted Risks / Intentional Choices

1. **`docker-compose.yml` uses `POSTGRES_PASSWORD: localdev` and `DATABASE_URL: ...localdev@...`** — This is a local-development-only credential. It is hardcoded for developer convenience and is not a production secret. No action required.

2. **`docker-compose.yml` uses `JWT_SECRET_KEY: dev-secret-change-in-production`** — This is a clearly labeled local-dev placeholder. The `config.py` Settings validator will raise a hard error if this value reaches a `production` environment (`APP_ENV=production`). No action required.

3. **`seed_billing.py` and `seed_tenants.py` contain fictional `subscription_id` values** (e.g., `mock-subscription-id`, `sub-acme-0001`) — These are synthetic identifiers used for local test data generation only. They are not GUIDs and do not correspond to real Azure resources.

---

## .gitignore Coverage

| Pattern category         | Covered? |
|--------------------------|----------|
| `.env` and all variants  | Yes — `*.local`, `.env`, `.env.*`, `!.env.example` |
| `backend/.env`           | Yes — `.env` and `.env.*` match recursively |
| `frontend/.env`          | Yes — `.env` and `.env.*` match recursively |
| Python artifacts         | Yes — `__pycache__/`, `*.py[cod]`, `*.pyo`, `.venv/`, `venv/`, `env/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`, `htmlcov/`, `.coverage`, `*.cover`, `.ruff_cache/` |
| Node / frontend builds   | Yes — `node_modules/`, `frontend/dist/`, `frontend/.vite/`, `*.tsbuildinfo` |
| Editor files             | Yes — `.DS_Store`, `Thumbs.db`, `*.swp`, `*.swo`, `.idea/`, `.vscode/` |
| Logs                     | Yes — `*.log`, `logs/` |
| Certificates and keys    | Yes — `*.pem`, `*.key`, `*.cert`, `*.crt`, `*.p12`, `*.pfx` |
| Docker overrides         | Yes — `docker-compose.override.yml` |

---

## .env.example Coverage

All 27 `Settings` fields defined in `backend/app/core/config.py` are documented in `.env.example` with safe placeholder values:

| Field | Present in .env.example |
|-------|------------------------|
| `APP_ENV` | Yes |
| `DEBUG` | Yes |
| `DATABASE_URL` | Yes |
| `REDIS_URL` | Yes |
| `JWT_SECRET_KEY` | Yes |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Yes |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Yes |
| `CORS_ORIGINS` | Yes |
| `FIRST_ADMIN_EMAIL` | Yes |
| `FIRST_ADMIN_PASSWORD` | Yes |
| `AZURE_SUBSCRIPTION_ID` | Yes |
| `AZURE_CLIENT_ID` | Yes |
| `AZURE_TENANT_ID` | Yes |
| `AZURE_CLIENT_SECRET` | Yes |
| `AZURE_SUBSCRIPTION_SCOPE` | Yes |
| `MOCK_AZURE` | Yes |
| `ANTHROPIC_API_KEY` | Yes |
| `ANTHROPIC_MODEL` | Yes |
| `AZURE_OPENAI_ENDPOINT` | Yes |
| `AZURE_OPENAI_API_KEY` | Yes |
| `AZURE_OPENAI_DEPLOYMENT` | Yes |
| `LLM_DAILY_CALL_LIMIT` | Yes |
| `LLM_MIN_MONTHLY_SPEND_THRESHOLD` | Yes |
| `SMTP_HOST` | Yes |
| `SMTP_PORT` | Yes |
| `SMTP_USER` | Yes |
| `SMTP_PASSWORD` | Yes |
| `SMTP_FROM` | Yes |
| `SMTP_START_TLS` | Yes |

---

## Checklist for Public Upload

- [x] No real credentials in any tracked source file
- [x] No real Azure subscription IDs (seed scripts use obvious mock values like `sub-acme-0001`)
- [x] No real API keys in tracked files (real key in `.env.local` is gitignored)
- [x] `.gitignore` covers all `.env` file variants
- [x] `.env.example` has all required variables with safe placeholders and documentation
- [x] `README.md` explains how to run with `MOCK_AZURE=true` (no Azure needed) and how to skip AI features (leave `ANTHROPIC_API_KEY` blank)
- [x] No personal email addresses in tracked source files
- [x] `docker-compose.yml` uses only local-dev credentials (clearly labeled, dev-only)
- [x] `docker-compose.prod.yml` contains no hardcoded credentials

---

## Recommended Manual Action Before First Push

**Rotate the Anthropic API key.** Even though `.env.local` is gitignored and was never committed, the key value at `sk-ant-api03-YpxkaqedDyfT3bMtPcej7KtljX2i3LAixvnqgCa3-...` should be considered exposed (shell history, process lists, editor sessions). Revoke it at https://console.anthropic.com and replace with a new key in `.env.local`.
