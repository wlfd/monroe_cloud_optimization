# Presentation Outline -- CloudCost

Course: CS 701 -- Special Projects in Computer Science S II
Project: Cloud Infrastructure Cost Optimization Platform
Sponsor: Fileread

---

## Design Notes

- **Color scheme:** Dark navy (#1e293b) primary, teal (#0d9488) accent, white text on dark backgrounds
- **Font:** Sans-serif throughout (Calibri or Inter), minimum 24pt for body text, 36pt for titles
- **Transitions:** Consistent fade or push transition between all slides
- **Graphics:** Architecture diagrams, ERD excerpt, code snippets in monospace, data flow arrows
- **Rule:** Maximum 6 bullet points per slide, approximately 6 words per bullet

---

## Slide 1: Title Slide

**Title:** CloudCost -- Azure Cloud Cost Optimization Platform

**Bullets:**
- CS 701 Special Projects
- [Student Name]
- Spring 2026
- Sponsor: Fileread

**Speaker Notes:**
Good morning. My project is CloudCost, a SaaS platform that helps engineering and finance teams understand and reduce their Azure cloud spending. This was built for Fileread, a seed-stage legal tech company with approximately 30 internal tenants and growing Azure costs.

**Visual:** CloudCost logo or Azure cloud icon on dark background.

---

## Slide 2: Problem Statement

**Title:** The Problem

**Bullets:**
- Cloud costs grow unpredictably
- No visibility into per-team spending
- Manual tracking in spreadsheets
- Anomalies discovered after the bill
- No automated cost-saving recommendations

**Speaker Notes:**
Organizations using Azure often lack visibility into where their money is going. Costs grow unpredictably, anomalies are discovered only after the monthly bill arrives, and there is no systematic way to attribute costs to specific teams or generate optimization recommendations. Fileread was tracking everything manually in spreadsheets.

**Visual:** Icon of a rising cost chart with a question mark overlay.

---

## Slide 3: Solution Overview

**Title:** CloudCost Platform

**Bullets:**
- Automated Azure billing ingestion
- Real-time cost monitoring dashboard
- Statistical anomaly detection
- AI-powered optimization recommendations
- Multi-tenant cost attribution
- Budget alerting with notifications

**Speaker Notes:**
CloudCost addresses all of these problems in a single hosted platform. It automatically ingests Azure billing data every four hours, detects cost anomalies using statistical baselines, generates AI-powered recommendations using Claude, and attributes costs to internal tenants using tag-based allocation rules. Budget thresholds trigger alerts via email or webhook.

**Visual:** Platform feature overview diagram with six connected boxes.

---

## Slide 4: System Architecture

**Title:** Architecture

**Bullets:**
- React 19 SPA (browser)
- FastAPI REST API (Python 3.12)
- PostgreSQL 15 (primary data store)
- Redis 7 (cache and counters)
- Azure Cost Management API
- Anthropic Claude / Azure OpenAI

**Speaker Notes:**
The architecture follows a standard three-tier pattern. The React frontend communicates with the FastAPI backend over REST with JWT authentication. The backend uses async SQLAlchemy against PostgreSQL for all persistent data and Redis for recommendation caching. External integrations include the Azure Cost Management API for billing data and Anthropic Claude for AI recommendations with Azure OpenAI as a fallback.

**Visual:** Architecture block diagram showing Browser -> FastAPI -> PostgreSQL/Redis -> Azure APIs.

---

## Slide 5: Technology Stack

**Title:** Technology Stack

**Bullets:**
- Backend: FastAPI, SQLAlchemy 2.0, Alembic
- Frontend: React 19, TypeScript, TanStack Query
- UI: shadcn/ui, Tailwind CSS, Recharts
- Database: PostgreSQL 15 (async)
- AI: Anthropic Claude + Azure OpenAI fallback
- DevOps: Docker Compose, GitHub Actions CI

**Speaker Notes:**
The technology choices were driven by performance and developer experience. FastAPI with async SQLAlchemy provides high-throughput API endpoints. React 19 with TanStack Query handles server state management efficiently. The AI layer uses Claude as the primary provider with automatic fallback to Azure OpenAI if the primary fails.

**Visual:** Tech stack logos arranged in a grid.

---

## Slide 6: Database Design

**Title:** Database Design -- 3NF Normalized

**Bullets:**
- 14 tables, all UUID primary keys
- Normalized to Third Normal Form
- 3 documented denormalization trade-offs
- 7 Alembic migrations (versioned schema)
- Indexed for dashboard query performance
- Full ERD with relationship documentation

**Speaker Notes:**
The database contains 14 tables normalized to Third Normal Form with three documented trade-offs. For example, budget alert events snapshot the budget amount at trigger time to preserve an immutable audit record even if the budget is later modified. All tables use UUID primary keys. The schema is managed through seven Alembic migrations, and key columns are indexed for dashboard query performance.

**Visual:** Excerpt from the Mermaid ERD showing 4-5 core tables and their relationships.

---

## Slide 7: Cost Ingestion Pipeline

**Title:** Feature: Cost Ingestion

**Bullets:**
- Azure Cost Management API integration
- 4-hour automated schedule (APScheduler)
- 24-month historical backfill capability
- Idempotent upsert (INSERT ON CONFLICT)
- Stale run recovery on startup
- Mock mode for local development

**Speaker Notes:**
The ingestion pipeline pulls billing data from Azure every four hours using APScheduler. Records are upserted using PostgreSQL's INSERT ON CONFLICT to handle duplicate data gracefully. On startup, the system detects and recovers stale runs that were interrupted. A mock mode generates synthetic data for development without Azure credentials.

**Visual:** Data flow diagram: Azure API -> Ingestion Service -> billing_records table.

---

## Slide 8: Anomaly Detection

**Title:** Feature: Anomaly Detection

**Bullets:**
- 30-day rolling cost baseline
- Deviation threshold: 20% and $100/month
- Severity: critical, high, medium
- Auto-resolve when condition clears
- Status lifecycle: new -> investigating -> resolved
- Idempotent detection (no duplicate alerts)

**Speaker Notes:**
Anomaly detection runs automatically after each ingestion. The algorithm computes a 30-day rolling average per service and resource group, then flags any day where spending exceeds the baseline by 20 percent AND the estimated monthly impact exceeds $100. Severity is classified as critical above $1,000, high above $500, and medium above $100. Anomalies auto-resolve when the condition clears.

**Visual:** Chart showing baseline cost line with a spike flagged as an anomaly.

---

## Slide 9: AI Recommendations

**Title:** Feature: AI-Powered Recommendations

**Bullets:**
- Daily batch at 02:00 UTC
- Anthropic Claude with structured output
- Azure OpenAI automatic fallback
- Redis cache (24-hour TTL per resource)
- Daily call limit with counter
- Categories: right-sizing, idle, reserved, storage

**Speaker Notes:**
Every day at 2 AM UTC, the recommendation engine qualifies resources with monthly spend above a configurable threshold, then sends each resource's 30-day cost history to Claude. The response is forced into a structured schema using tool_choice, extracting category, explanation, estimated savings, and confidence score. Results are cached in Redis for 24 hours. If Claude fails after three retries, the system falls back to Azure OpenAI automatically.

**Visual:** Flow diagram: Resource qualification -> Claude API -> Structured output -> Dashboard.

---

## Slide 10: Multi-Tenant Attribution

**Title:** Feature: Cost Attribution

**Bullets:**
- Tag-based tenant identification
- Priority-ordered allocation rules
- Drag-to-reorder rule management
- Per-tenant monthly cost reports
- Top service category per tenant
- Manual attribution run trigger

**Speaker Notes:**
CloudCost attributes billing records to internal tenants using tag-based allocation rules. Rules are matched in priority order -- the first matching rule wins. Administrators can create, edit, and reorder rules using a drag-and-drop interface. The system generates per-tenant monthly reports showing total cost and the top spending service category.

**Visual:** Diagram showing billing records flowing through allocation rules to tenant cost buckets.

---

## Slide 11: Budgets and Alerts

**Title:** Feature: Budgets and Alerts

**Bullets:**
- Per-tenant or per-subscription budgets
- Multiple thresholds per budget (80%, 100%)
- Automated threshold checking (6x/day)
- Email notifications (SMTP)
- Webhook notifications (HMAC-signed)
- 3-attempt retry for failed webhooks

**Speaker Notes:**
Administrators configure budgets scoped to subscriptions or tenants with multiple threshold percentages. The system checks spend against thresholds six times per day after ingestion completes. When a threshold is crossed, alerts are dispatched via email or HMAC-signed webhooks. Failed webhook deliveries are retried up to three times with a 15-minute interval.

**Visual:** Budget bar chart showing spend approaching 80% and 100% threshold lines.

---

## Slide 12: Security Implementation

**Title:** Security

**Bullets:**
- JWT access + HttpOnly refresh tokens
- Four RBAC roles (admin, devops, finance, viewer)
- Brute-force lockout (5 attempts, 15 min)
- Argon2 password hashing
- HMAC-signed webhooks (SHA-256)
- Webhook secrets redacted in API responses

**Speaker Notes:**
Authentication uses JWT access tokens stored in memory only, paired with HttpOnly refresh token cookies. Four role-based access levels control what each user can see and do. The system locks accounts after five failed login attempts for fifteen minutes. Webhook secrets are stored encrypted and redacted from all API responses to prevent credential leakage. Seven security vulnerabilities were identified during an architecture review and all were patched.

**Visual:** Security architecture diagram showing token flow and role hierarchy.

---

## Slide 13: Error Handling and Resilience

**Title:** Error Handling

**Bullets:**
- Tenacity retry for external APIs
- LLM provider fallback chain
- Stale ingestion run recovery
- Per-budget error isolation
- Notification delivery retry queue
- Custom exception hierarchy

**Speaker Notes:**
The system is designed for resilience at every integration point. Azure API calls use Tenacity retry with exponential backoff. The AI recommendation pipeline falls back from Claude to Azure OpenAI on failure. Stale ingestion runs are detected and recovered on startup. Budget threshold checking uses isolated database sessions so one budget failure does not affect others. Failed notification deliveries enter a retry queue.

**Visual:** Error handling flow showing retry paths and fallback chains.

---

## Slide 14: Testing Strategy

**Title:** Testing

**Bullets:**
- 170 backend tests (pytest-asyncio)
- 116 frontend tests (Vitest + RTL)
- MSW for API mocking
- GitHub Actions CI pipeline
- Lint + format + type-check gates
- All tests passing (99.7% pass rate)

**Speaker Notes:**
The test suite includes 170 backend tests covering all nine service modules and API routes, plus 116 frontend tests covering all eight pages, API hooks, and the auth context. Backend tests use AsyncMock for database and Redis isolation. Frontend tests use Mock Service Worker for network-level API mocking. The CI pipeline runs lint, format check, type check, build verification, and all tests on every push and pull request.

**Visual:** Test results summary table or CI pipeline diagram.

---

## Slide 15: Bug Resolution Highlights

**Title:** Bugs Found and Resolved

**Bullets:**
- 9 bugs tracked and resolved
- 7 security vulnerabilities patched
- Cross-browser drag-and-drop fix
- Timezone off-by-one date correction
- CI test environment stabilization
- Zero open bugs at submission

**Speaker Notes:**
Throughout development, nine bugs were formally tracked and resolved. The most significant was an architecture review that identified seven security vulnerabilities including exposed webhook secrets, dead brute-force lockout code, and session corruption in the budget checker. Other notable fixes include replacing HTML5 drag events with pointer events for cross-browser compatibility and correcting a timezone parsing issue that shifted dates by one day for users west of UTC.

**Visual:** Bug summary table (ID, severity, status) or resolution timeline.

---

## Slide 16: Live Demo

**Title:** Live Demo

**Bullets:**
- Login as admin
- Dashboard: cost summary and trends
- Trigger manual ingestion
- View detected anomalies
- Browse AI recommendations
- Configure budgets and alerts

**Speaker Notes:**
Let me walk through the application. First, we log in with the admin account. The dashboard shows the month-to-date cost summary, a daily spending trend chart, cost breakdown by service, and the top ten resources. I will trigger a manual ingestion to show the pipeline in action, then navigate to the anomalies page to show detected cost spikes. Next, we will look at the AI-generated recommendations and finally configure a budget with threshold alerts.

**Visual:** Live application demonstration.

---

## Slide 17: Challenges and Lessons Learned

**Title:** Challenges

**Bullets:**
- Async SQLAlchemy session management
- jsdom limitations for chart testing
- HTML5 drag API cross-browser issues
- LLM structured output enforcement
- JWT refresh token race conditions
- Transaction coupling for data integrity

**Speaker Notes:**
The biggest technical challenges were around async database session management, particularly ensuring sessions were not shared across budget check iterations. Testing charts in jsdom required polyfilling ResizeObserver and pointer capture APIs. The HTML5 drag-and-drop API proved unreliable for table row reordering across browsers, requiring a rewrite to pointer events. Enforcing structured output from the LLM required using Claude's tool_choice feature.

**Visual:** Challenge and resolution comparison table.

---

## Slide 18: Future Enhancements

**Title:** Future Work

**Bullets:**
- Append-only audit logging
- End-to-end test suite (Playwright)
- Structured logging and observability
- Kubernetes deployment (AKS)
- Multi-cloud support (AWS, GCP)
- Cost forecasting with ML models

**Speaker Notes:**
The next priorities are audit logging for compliance, end-to-end testing with Playwright for critical user flows, structured JSON logging for production observability, and container orchestration via Azure Kubernetes Service. Longer-term goals include multi-cloud support for AWS and GCP cost data and machine learning-based cost forecasting.

**Visual:** Roadmap timeline or feature priority matrix.

---

## Slide 19: Questions

**Title:** Questions?

**Bullets:**
- Repository: github.com/[repo-url]
- Stack: FastAPI + React 19 + PostgreSQL
- 286 automated tests
- 14 database tables (3NF)
- 9 service modules

**Speaker Notes:**
Thank you for your time. I am happy to answer any questions about the architecture, implementation decisions, or demonstrate any specific feature in more detail.

**Visual:** Contact information and repository link on clean background.
