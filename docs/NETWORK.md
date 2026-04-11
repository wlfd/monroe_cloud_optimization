# CloudCost — Network Diagram Documentation

**File:** `docs/NETWORK.drawio`
**Submission:** CS 701 Academic Submission
**Date:** 2026-04-10

---

## Page Guide

`NETWORK.drawio` contains two pages. Switch between them using the tabs at the bottom of the draw.io window (or the page-selector panel on the left when using the desktop app).

### Page 1 — Dev - Docker Compose

Shows the **current local development setup** as defined in `docker-compose.yml`. Every component on this page is fully implemented and running. Services communicate over a single Docker bridge network (`app_network`); only ports 3000 (frontend) and 8000 (backend API) are exposed to the host machine. The `migrate` and `seed` containers are shown as dashed utility boxes because they run once on startup and then exit.

### Page 2 — Prod - Azure Architecture

Shows the **target production deployment on Azure**. Components whose labels include `[PLANNED]` are designed and documented but **not yet implemented** — they have a dashed border and lighter fill to distinguish them from live components. Implemented components use a solid blue border. The diagram covers:

- Edge / Public Zone: Azure Front Door (CDN + load balancer) and a WAF (Application Gateway) [PLANNED]
- Application Zone: React Frontend and FastAPI Backend both running as Azure Container Apps
- Data Zone: Azure Database for PostgreSQL Flexible Server (primary), a read replica [PLANNED], Azure Cache for Redis, and Azure Container Registry
- Management & Security Zone [entirely PLANNED]: VPN Gateway, Bastion, Key Vault, Microsoft Sentinel (SIEM), Microsoft Defender (IDS/IPS), and Azure Monitor / Log Analytics
- CI/CD Zone: GitHub Actions pipeline producing Docker images pushed to the Container Registry

### Color coding at a glance

| Style | Meaning |
|---|---|
| Solid blue fill, solid border | Implemented component — running today |
| Light blue fill, dashed border, italic text | Planned component — not yet implemented |
| Yellow fill, dashed border, italic text | Security component (planned) |
| Yellow cylinder | PostgreSQL database |
| Yellow dashed cylinder | Database read replica (planned) |
| Red cylinder | Redis cache |
| Gray rect | External service (internet) |
| Purple rect | Client device / browser |
| Blue dashed outline | Azure zone or Docker network boundary |

---

## Table of Contents

1. [Page Guide](#page-guide)
2. [How to Open This Diagram](#1-how-to-open-this-diagram)
3. [Component Justification](#2-component-justification)
4. [Network Security Notes](#3-network-security-notes)
5. [Production vs. Development Note](#4-production-vs-development-note)
6. [Draw.io Setup Instructions](#5-drawio-setup-instructions)

---

## 1. How to Open This Diagram

### Web (recommended — no installation required)

1. Open your browser and navigate to **https://app.diagrams.net**
2. On the start screen, click **"Open Existing Diagram"** (or the folder icon in the top-left after a diagram is already open: File > Open From > Device...)
3. Browse to `docs/NETWORK.drawio` in your local copy of this repository and select it
4. Alternatively, drag and drop `NETWORK.drawio` directly onto the app.diagrams.net browser tab — the diagram will open immediately

### Desktop application (optional, for offline editing)

1. Download the draw.io desktop app from: **https://github.com/jgraph/drawio-desktop/releases**
2. Choose the release asset that matches your OS:
   - macOS: download the `.dmg` file, open it, drag draw.io to Applications
   - Windows: download the `.exe` installer
   - Linux: download the `.AppImage` or `.deb`
3. Launch the application, choose **File > Open** and select `docs/NETWORK.drawio`

### Exporting the diagram

- **PNG (raster image):** File > Export As > PNG — choose resolution (300 DPI recommended for printing)
- **SVG (vector, scales to any size):** File > Export As > SVG — best for embedding in digital documents
- **PDF:** File > Export As > PDF — suitable for direct print or submission
- All export formats preserve the full diagram including labels and arrows

### Basic editing

- **Select a shape:** single-click
- **Move a shape:** click and drag
- **Edit text on a shape:** double-click the shape
- **Resize a shape:** select it, then drag any of the blue handles at the corners and edges
- **Pan the canvas:** hold `Space` and drag, or use the scroll bars
- **Zoom in/out:** `Ctrl +` / `Ctrl -` (Windows/Linux) or `Cmd +` / `Cmd -` (macOS), or use the zoom control at the bottom of the window

---

## 2. Component Justification

### User's Browser

The user's browser (Chrome, Firefox, or Safari) is the entry point for every CloudCost user. It renders the React Single Page Application delivered by the frontend container and communicates with the FastAPI backend over HTTPS using JWT Bearer tokens stored in memory. Including the browser explicitly in the diagram makes the trust boundary and attack surface of the client tier visible.

### React Frontend Container (Vite)

The React 19 frontend is packaged as a Docker container running the Vite development server on port 3000 (exposed to the host). It serves the TypeScript/Tailwind SPA and uses TanStack Query with Axios to make authenticated REST calls to the backend API. In development it runs as the `builder` Docker stage; in production it is replaced by an Nginx static-file server.

### FastAPI Backend Container (Uvicorn)

The FastAPI backend (Python 3.12, Uvicorn ASGI server) is the central hub of the system, exposed on port 8000. It implements all business logic: REST endpoints under `/api/v1/*`, an embedded APScheduler for periodic jobs (cost ingestion every 4 hours, AI recommendations daily at 02:00 UTC, budget checks every 4 hours, webhook retry every 15 minutes), and outbound integrations with Azure, AI providers, SMTP, and webhook targets. Every significant network flow in the diagram either originates from or terminates at this container.

### PostgreSQL 15 Container

PostgreSQL 15 is the primary persistent data store for CloudCost. It holds all domain data: users and sessions, billing/cost records from ingested Azure data, AI recommendation results, tenant attribution rules, budget definitions, and notification delivery logs. The port (5432) is mapped to the host in development but is intentionally internal-only in a production deployment; the backend accesses it via async SQLAlchemy 2.0 using the `asyncpg` driver.

### Redis 7 Container

Redis 7 (Alpine variant) provides two distinct services: a short-lived cache for AI recommendation results (avoiding redundant and costly LLM calls within a cache window) and a job-deduplication mechanism that prevents concurrent ingestion runs from trampling each other. Port 6379 is internal to the Docker bridge network and is never exposed to the host in production. The backend connects using the `REDIS_URL` environment variable.

### Alembic Migrate Container

The `migrate` service uses the same backend Docker image but runs a single command — `alembic upgrade head` — on startup and then exits. It applies all outstanding database schema migrations before the API and seed containers start, ensuring the schema is always at the correct version. It is shown as a dashed, italic box to communicate its ephemeral, one-shot nature. It depends on the PostgreSQL health check passing before it starts.

### Seed Admin Container

The `seed` service (also shown as a dashed utility box) runs `python -m app.scripts.seed_admin` once after migrations complete. It creates the initial `admin@cloudcost.local` administrator account if it does not already exist, making the application immediately usable after a fresh `docker compose up`. Like `migrate`, it exits after its single task and is not a long-running process.

### Azure Cost Management API

The Azure Cost Management API (`management.azure.com`) is the authoritative source of billing data for CloudCost. The FastAPI backend polls it on a 4-hour APScheduler interval using OAuth2 Bearer tokens obtained via the `azure-identity` service principal credentials (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`). In local development this integration is replaced by a mock client when `MOCK_AZURE=true`, so no real Azure credentials are required.

### Anthropic Claude API

The Anthropic Claude API is the primary AI provider used by CloudCost to generate actionable cost-saving recommendations. Each day at 02:00 UTC the backend selects resources with monthly spend above the `LLM_MIN_MONTHLY_SPEND_THRESHOLD` (default $50), sends cost context to Claude via the Anthropic API (`ANTHROPIC_API_KEY`, model `claude-sonnet-4-6`), and stores the generated recommendations in PostgreSQL. A daily call limit (`LLM_DAILY_CALL_LIMIT`, default 100) guards against runaway API costs.

### Azure OpenAI API (fallback)

Azure OpenAI (`{resource}.openai.azure.com`) is the secondary AI provider, used when an Anthropic API key is not configured or as an organizational preference. It accepts the same recommendation-generation requests via `AZURE_OPENAI_API_KEY` and a named deployment (default `gpt-4o`). Marking it as `[fallback]` in the diagram accurately reflects its role: CloudCost uses whichever LLM is configured, with Anthropic Claude as the primary.

### SMTP Server

The SMTP server (port 587, STARTTLS) handles outbound email notifications — budget threshold alerts, anomaly notifications, and report delivery. The backend is compatible with any standards-compliant SMTP relay: SendGrid, Amazon SES, Azure Communication Services, or self-hosted Postfix. Connection details are supplied via `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, and `SMTP_PASSWORD` environment variables. STARTTLS is enabled by default (`SMTP_START_TLS=true`).

### Webhook Target URLs

Webhook target URLs are arbitrary HTTPS endpoints registered by CloudCost users to receive real-time event notifications (budget breaches, new anomalies, recommendation summaries). The backend signs each outgoing POST body with HMAC-SHA256 so recipients can verify authenticity. Failed deliveries are automatically retried on a 15-minute APScheduler interval, with exponential back-off logic to avoid hammering unavailable targets.

### Docker Bridge Network (app_network)

Docker Compose creates a default bridge network (`app_network`) that connects all services — `db`, `redis`, `migrate`, `seed`, `api`, and `frontend` — using their service names as DNS hostnames. This means the API connects to PostgreSQL at `db:5432` and Redis at `redis:6379`, eliminating the need for IP address configuration. Only the ports explicitly listed under `ports:` in `docker-compose.yml` (5432, 6379, 8000, 3000) are reachable from the host machine; everything else is network-internal.

---

## 3. Network Security Notes

### Internet-facing vs. internal-only ports

| Port | Service | Exposure |
|------|---------|----------|
| 3000 | React Frontend (Vite dev server) | **Host-exposed in dev** — mapped `3000:3000`; should be behind a reverse proxy/CDN in production |
| 8000 | FastAPI Backend (Uvicorn) | **Host-exposed in dev** — mapped `8000:8000`; should be behind a reverse proxy in production |
| 5432 | PostgreSQL | **Internal only** — accessible only within the Docker bridge network (`db:5432`) |
| 6379 | Redis | **Internal only** — accessible only within the Docker bridge network (`redis:6379`) |
| 443 | All external APIs (Azure, Anthropic, SMTP) | **Outbound only** — initiated by the backend container, no inbound exposure |
| 587 | SMTP (STARTTLS) | **Outbound only** — initiated by the backend container for email delivery |

In a production deployment, ports 3000 and 8000 would not be directly exposed. They would sit behind an Azure Front Door or Application Gateway that terminates TLS and enforces WAF rules.

### JWT token protection

Every non-public API endpoint requires a valid JWT Bearer token in the `Authorization` header. Access tokens are signed with `JWT_SECRET_KEY` using HS256, expire after 60 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`), and are stored in-memory only in the browser — never in `localStorage` or `sessionStorage`, which prevents XSS-based token theft. When an access token expires, the frontend silently re-authenticates using the HttpOnly refresh token cookie (7-day lifetime, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`), which is inaccessible to JavaScript. The JWT payload includes the user's role (`admin`, `devops`, `finance`, or `viewer`), enabling endpoint-level authorization checks without an extra database query.

### HMAC webhook signature protection

When the FastAPI backend dispatches a webhook notification, it computes an HMAC-SHA256 digest over the raw POST body using a per-channel secret key stored in PostgreSQL. The signature is sent in the `X-CloudCost-Signature` HTTP header. Receiving services must validate this signature before processing the payload, ensuring that webhook events cannot be forged by a third party who intercepts or guesses the endpoint URL.

### TLS/HTTPS requirements

- All communication between the browser and the frontend/API uses HTTPS in production (HTTP in local Docker dev where both parties are on localhost)
- All outbound connections from the backend to external APIs (Azure Cost Management, Anthropic, Azure OpenAI, webhook targets) use HTTPS/TLS 1.2+ enforced by the Python `requests`/`httpx` libraries
- SMTP uses STARTTLS on port 587, upgrading the plaintext connection to TLS before credentials or message content are transmitted
- The `JWT_SECRET_KEY` must be set to a strong random value in production (`openssl rand -hex 64`); the application validates at startup that the default placeholder value is not used when `APP_ENV=production`

---

## 4. Production vs. Development Note

This section maps the two diagram pages to their operational contexts. See **Page 1** (`Dev - Docker Compose`) for the development topology and **Page 2** (`Prod - Azure Architecture`) for the production target.

### Development (Page 1 — Docker Compose)

In the Docker Compose development environment all six service containers run on a single host machine connected by one Docker bridge network (`app_network`). Ports 3000 and 8000 are mapped to the host for direct browser access. HTTP (not HTTPS) is used for browser-to-frontend and browser-to-API traffic because both sides are on `localhost`. `MOCK_AZURE=true` is set by default, so no real Azure subscription credentials are needed. The `migrate` and `seed` containers run once and exit; the `api` container uses Uvicorn's `--reload` flag for hot-reload on code changes.

### Production target (Page 2 — Azure)

A production deployment of CloudCost on Azure replaces the single-host Docker Compose topology with a fully managed, network-isolated architecture. Page 2 of the diagram shows this target state; components marked `[PLANNED]` are designed but not yet implemented (they appear with dashed borders and italic labels).

| Dev component (Page 1) | Production equivalent (Page 2) | Status |
|---|---|---|
| React Vite dev server (port 3000) | Azure Container Apps — Nginx static stage | Implemented |
| FastAPI Uvicorn container (port 8000) | Azure Container Apps — auto-scaling, managed TLS | Implemented |
| PostgreSQL 15 container | Azure Database for PostgreSQL Flexible Server (primary + read replica) | Primary implemented; replica planned |
| Redis 7 container | Azure Cache for Redis (managed, private endpoint) | Implemented |
| Docker bridge network | Azure Virtual Network (VNET) + Container Apps Environment | Planned |
| Host-exposed ports 3000 / 8000 | Azure Front Door (CDN + WAF) terminating TLS | Front Door implemented; WAF planned |
| SMTP container | Azure Communication Services Email or SendGrid via `SMTP_*` env vars | Implemented (external SMTP) |
| — | Azure Key Vault, Sentinel, Defender, Bastion, VPN Gateway, Monitor | All planned |

In the target production topology the PostgreSQL and Redis endpoints sit on private endpoints within the VNET and are unreachable from the public internet. The API and frontend are exposed only through Azure Front Door, which enforces HTTPS, rate limiting, and WAF rule sets (WAF currently planned).

---

## 5. Draw.io Setup Instructions

### Opening the diagram (web — recommended for viewing)

1. Go to **https://app.diagrams.net** in any modern browser
2. No account or login is required
3. Click **"Open Existing Diagram"** on the start screen
4. Select `docs/NETWORK.drawio` from your filesystem
5. The diagram opens immediately in the browser-based editor

### Installing the desktop application (recommended for editing)

1. Visit **https://github.com/jgraph/drawio-desktop/releases**
2. Find the latest stable release (look for the most recent tag, e.g., `v24.x.x`)
3. Download the appropriate asset:
   - **macOS:** `draw.io-x.x.x-universal.dmg` (supports both Intel and Apple Silicon)
   - **Windows:** `draw.io-x.x.x-windows-installer.exe`
   - **Linux (Debian/Ubuntu):** `draw.io-x.x.x-amd64.deb`
   - **Linux (AppImage, any distro):** `draw.io-x.x.x-x86_64.AppImage`
4. macOS: open the `.dmg`, drag `draw.io.app` to `/Applications`, then launch from Launchpad or Spotlight
5. Open the diagram: **File > Open** and navigate to `docs/NETWORK.drawio`

### Navigating the canvas

| Action | Keyboard / Mouse |
|---|---|
| Zoom in | `Ctrl +` (Windows/Linux) or `Cmd +` (macOS) |
| Zoom out | `Ctrl -` / `Cmd -` |
| Fit diagram to window | `Ctrl Shift H` / `Cmd Shift H` |
| Pan (scroll) | Hold `Space` and drag, or use scroll bars |
| Pan (middle mouse) | Hold middle mouse button and drag |
| Select all | `Ctrl A` / `Cmd A` |
| Undo | `Ctrl Z` / `Cmd Z` |
| Redo | `Ctrl Y` / `Cmd Shift Z` |

### Changing colors and styles

1. Click a shape to select it
2. In the right-hand panel, click the **"Style"** tab (or right-click > **Edit Style...**)
3. To change fill color: click the colored square next to "Fill" in the Format panel
4. To change border color: click the square next to "Line"
5. To edit the raw style string: right-click the shape > **Edit Style** — paste a new style string and click OK
6. To copy a style from one shape to another: right-click source shape > **Edit Style**, copy the string, right-click target > **Edit Style**, paste

### Adding a new shape

1. From the left panel, drag a shape from the shape library onto the canvas
2. Or: double-click an empty area of the canvas to open the shape picker search box, type a shape name (e.g., "cylinder"), and press Enter to insert
3. To add a connector: hover over a shape until blue connection arrows appear at the edges, then drag from an arrow to a target shape

### Exporting the diagram

| Format | Steps |
|---|---|
| PNG | File > Export As > PNG > choose scale/resolution > Export |
| SVG | File > Export As > SVG > Export (scales losslessly to any size) |
| PDF | File > Export As > PDF > Export |
| JPEG | File > Export As > JPEG > Export |

For academic submission, **SVG** is recommended for digital documents (Word, LaTeX) and **PNG at 300 DPI** for printed output.

### File format note

`.drawio` files are plain XML. You can open `NETWORK.drawio` in any text editor to inspect or programmatically modify the diagram. Each shape and connection is an `mxCell` element with geometry and style attributes. This means the diagram can be version-controlled with git and diffs are human-readable. If you ask Claude Code to add, remove, or modify a component, it can edit the XML directly without requiring the draw.io GUI.
