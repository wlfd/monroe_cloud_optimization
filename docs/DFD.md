# Data Flow Diagrams — CloudCost Platform

## Overview

Data Flow Diagrams (DFDs) model how data moves through a system. They use four building blocks: external entities (the actors or systems outside the software boundary that send or receive data), processes (the transformations the system applies to data), data stores (persistent repositories where data is held at rest), and data flows (the labeled arrows that carry data between these elements).

Two levels of DFD were produced for the CloudCost Azure cost-optimization platform as part of the CS 701 academic submission:

- **Level 0 (Context Diagram)** — treats the entire platform as a single black-box process and shows only the external boundary: who or what communicates with the system and what data crosses each boundary.
- **Level 1 DFD** — decomposes the platform into its eight major internal processes (P1–P8), seven data stores (D1–D7), and the same six external entities, then traces every significant data flow between them.

Both diagrams are stored in `DFD.drawio` and can be opened for editing or export at **app.diagrams.net**.

---

## Level 0 — Context Diagram

The context diagram shows the CloudCost Platform as a single process surrounded by six external entities. Each entity is connected to the platform by one or more labelled flows.

### External Entities

| ID | Name | Role |
|----|------|------|
| E1 | Azure Cost Management API | Source of raw Azure billing data; the platform queries it on a date-range window and it returns daily cost records per resource. |
| E2 | Admin / DevOps User | Operators who log in, trigger manual ingestion runs, configure budgets and allocation rules, and review anomaly and ingestion-status dashboards. |
| E3 | Finance / Viewer User | Read-only stakeholders who log in to view cost reports, tenant attribution breakdowns, and AI-generated optimization recommendations. |
| E4 | Anthropic Claude / Azure OpenAI | External LLM APIs invoked once per qualifying resource per day. The platform sends a 30-day cost-history prompt and receives a structured JSON optimization recommendation. Azure OpenAI acts as a fallback when Anthropic fails all retries. |
| E5 | SMTP Server | Outbound email relay. The platform sends HTML alert emails for budget threshold breaches, anomaly detections, and ingestion-pipeline failures. |
| E6 | Webhook Endpoints | Customer-configured HTTP endpoints. The platform POST-s HMAC-SHA256-signed JSON payloads for the same three event types; failed webhooks are retried every 15 minutes up to three total attempts. |

### System Boundary Flows

| Direction | Data Crossing the Boundary |
|-----------|---------------------------|
| E1 → Platform | Raw billing records — daily cost rows per (subscription, resource group, service, meter category, usage date). |
| Platform → E1 | Billing query — parameterized date-range and subscription scope used to pull the incremental delta window (24h overlap applied to catch late-arriving records). |
| E2 → Platform | Login credentials (username + password); admin commands (manual ingestion trigger, budget create/edit, anomaly status updates, allocation-rule management). |
| Platform → E2 | JWT access token + HttpOnly refresh cookie; dashboard data: cost trend charts, active anomaly list, ingestion run log, recommendation list. |
| E3 → Platform | Login credentials; filter parameters (month, tenant ID, cost category) for the cost and attribution views. |
| Platform → E3 | Cost reports (daily/monthly aggregates by service and resource group); tenant attribution breakdowns (tagged + allocated spend, month-over-month delta); AI recommendations. |
| Platform → E4 | Resource cost context: resource metadata plus a 30-day daily cost history table, framed as a user prompt asking for an optimization recommendation. |
| E4 → Platform | Structured recommendation: `{ category, explanation, estimated_monthly_savings, confidence_score }` returned via Anthropic tool_use or Azure OpenAI JSON mode. |
| Platform → E5 | Rendered HTML email (budget alert, anomaly alert, or ingestion-failure alert) sent via aiosmtplib SMTP with optional STARTTLS. |
| Platform → E6 | HMAC-SHA256-signed JSON webhook payloads containing event_type, event_id, timestamp, and event-specific data fields. |

---

## Level 1 — Expanded DFD

The Level 1 diagram decomposes the platform into eight internal processes and seven data stores.

### Processes

**P1 — Authenticate Users**

Handles all login and session management for both E2 and E3. On a valid credential submission it reads the user record from D2, writes a new session/refresh-token row, and returns a short-lived JWT access token (60 min, in-memory) plus an HttpOnly refresh-token cookie (7 days). Four roles are supported: `admin`, `devops`, `finance`, `viewer`. Every subsequent API call validated by FastAPI's `get_current_user` dependency reads the token from D2 to check revocation.

**P2 — Ingest Billing Data** *(scheduled: every 4 hours; also triggered manually)*

The ingestion orchestrator. On first-ever run it delegates to a 24-month historical backfill (chunked into 30-day windows with QPU throttle). On subsequent runs it computes the incremental delta window (last successful run end − 24 h overlap, capped at 7 days) and fetches only new/updated records from E1. It upserts all rows into D1 using PostgreSQL `INSERT … ON CONFLICT DO UPDATE`. A process-local asyncio lock prevents concurrent runs. After a successful upsert, P2 synchronously triggers P4 (anomaly detection) and P6 (tenant attribution). On failure it creates an alert in D6 and calls P8 to broadcast an ingestion-failure notification.

**P3 — Monitor Costs**

Answers real-time queries from both E2 and E3 against D1. Produces: daily cost totals, rolling trend charts, cost-by-service breakdowns, cost-by-resource-group breakdowns, and a current-month summary. This process is read-only; it does not mutate any data store.

**P4 — Detect Anomalies** *(called post-ingestion by P2)*

Implements the 30-day rolling baseline algorithm. It reads the last 30 days from D1, computes a per-(service, resource_group) baseline daily average, then compares the most recent completed billing day against each baseline. Pairs that exceed both a 20% deviation threshold and a $100/month noise floor are classified as `medium`, `high`, or `critical` and upserted into D3. Previously open anomalies that no longer exceed the threshold are auto-resolved. Newly detected anomalies (not already open in D3) are forwarded as events to P8 for notification dispatch.

**P5 — Generate AI Recommendations** *(daily cron at 02:00 UTC; also triggered manually)*

The LLM pipeline. Queries D1 for all resources with current-month spend above the configurable threshold, ordered by spend descending (highest spenders processed first so the daily call budget covers the most impactful resources). For each qualifying resource, it first checks D4 (Redis cache, 24-hour TTL) for a cached result. On a cache miss it increments a daily Redis counter and, if under the daily call limit, calls E4 (Anthropic Claude Sonnet with forced tool_use structured output; Azure OpenAI as fallback). Results are cached in D4 and inserted as new Recommendation rows (using `generated_date = today` for logical daily replacement with no DELETE flash). The recommendations dashboard always queries the most recent `generated_date` via a MAX subquery.

**P6 — Attribute Tenant Costs** *(called post-ingestion by P2)*

Discovers tenant identities from the `tag` column of D1 and upserts new tenant profiles into D5. It then sums tagged spend per tenant and untagged spend for the current billing month. Allocation rules stored in D5 are applied in priority order to distribute untagged costs across tenants (three methods: `by_count`, `by_usage`, `manual_pct`). Final per-tenant totals (tagged + allocated) are upserted into the `tenant_attributions` table in D5 along with month-over-month delta versus prior period.

**P7 — Check Budget Thresholds** *(scheduled: every 4 hours, 1-hour offset after ingestion)*

Loads all active budgets from D6 and, for each, queries D1 for current-period spend (filtered by budget scope: subscription, resource group, service, or tag). Each budget's thresholds are evaluated in ascending percentage order. If current spend exceeds a threshold percentage and that threshold has not already fired in the current billing period, P7 writes an AlertEvent row to D6, stamps the threshold's `last_triggered_period`, and calls P8 to dispatch a notification to the threshold's linked channel.

**P8 — Deliver Notifications**

The unified notification dispatcher. Receives events from P4 (anomaly detected) and P7 (budget threshold crossed), and is also called by P2 on ingestion failure. For each event it reads the active notification channels from D7, renders a Jinja2 HTML template for email channels, builds a signed JSON payload for webhook channels, and attempts delivery. Each attempt is logged as a NotificationDelivery row in D7. A separate 15-minute scheduler job retries failed webhook deliveries (up to three total attempts) by re-reading stored payloads from D7 and re-signing them.

### Data Stores

| ID | Store | Contents |
|----|-------|----------|
| D1 | `billing_records` | Primary fact table. One row per (usage_date, subscription_id, resource_group, service_name, meter_category). Conflict-target upsert ensures idempotency on re-ingestion. |
| D2 | `users` / `user_sessions` | User accounts (hashed passwords, roles) and refresh-token session rows. Access tokens are in-memory only; D2 is the revocation source of truth. |
| D3 | `anomalies` | One row per (service_name, resource_group, detected_date). Stores baseline metrics, deviation percentages, estimated monthly impact, severity, and lifecycle status (new → investigating → resolved / dismissed). |
| D4 | `recommendations` (PostgreSQL) + Redis cache | Recommendation rows keyed by resource identity and `generated_date`. Redis holds 24-hour per-resource cache entries and a per-day LLM call counter; PostgreSQL holds the persistent recommendation history. |
| D5 | `tenant_profiles` / `allocation_rules` / `tenant_attributions` | Tenant discovery registry, allocation-rule configuration (target type, target value, distribution method, optional manual percentages), and the computed monthly attribution results. |
| D6 | `budgets` / `budget_thresholds` / `alert_events` | Budget definitions (scope, amount, period), per-budget threshold rows (percentage, linked notification channel, last-triggered period), and the historical alert-event log. |
| D7 | `notification_channels` / `notification_deliveries` | Channel configuration (email address or webhook URL + HMAC secret) and the full delivery log including attempt number, HTTP response code, stored payload (for webhook retries), and final status. |

### Key Data Flows

| Flow | Description |
|------|-------------|
| E2 → P1 → D2 → E2 | Login request authenticated, session written, token returned. |
| E1 → P2 → D1 | Raw billing records ingested and upserted idempotently. |
| P2 → P4 | Synchronous post-ingestion trigger for anomaly detection. |
| P2 → P6 | Synchronous post-ingestion trigger for tenant attribution. |
| D1 → P4 → D3 → P8 → D7 → E5/E6 | Anomaly detected: billing data analysed, anomaly upserted, notification dispatched. |
| D1 → P5 ↔ D4 ↔ E4 | Recommendations generated: billing read, Redis cache consulted, LLM called, result cached and stored. |
| D1 → P6 ↔ D5 | Tenant attribution: billing data partitioned by tag, rules applied, attribution rows upserted. |
| D6 → P7 → D6 + P8 | Budget check: active budgets read, spend compared, alert events written, notifications dispatched. |
| P8 → D7 + E5/E6 | Delivery attempt logged; webhook payloads HMAC-signed before POST. |

---

## Design Notes

**Why P2 triggers P4, P6, and P7 inline (not as separate scheduled jobs).**
Anomaly detection and tenant attribution must operate on fresh data. Running them as immediately chained steps after a successful upsert guarantees they always see the latest billing window without a race condition against the next scheduled trigger. P7 (budget) runs on its own 4h scheduler but uses a 1-hour offset from ingestion so that by the time it fires, P2, P4, and P6 have all completed and D1 contains the freshest data.

**Why Redis is co-located with D4 (recommendations).**
Redis serves two distinct but tightly coupled functions for the recommendation pipeline: a per-resource 24-hour result cache (avoids redundant LLM calls for resources whose cost history has not meaningfully changed) and a daily rolling call counter (enforces the configurable `LLM_DAILY_CALL_LIMIT`). Grouping them into D4 reflects that both are ephemeral control state for the same pipeline; the PostgreSQL `recommendations` table is the durable record.

**Why D5 combines three tables.**
`tenant_profiles`, `allocation_rules`, and `tenant_attributions` are all managed by a single service (`attribution.py`) and represent a single conceptual domain: the multi-tenant cost split. Grouping them keeps the DFD readable while accurately reflecting that P6 reads from all three and writes to two of them within one logical operation.

**Why D6 combines three tables.**
`budgets`, `budget_thresholds`, and `alert_events` form a tight hierarchy: a budget owns its thresholds, and threshold breaches produce alert events. P7 reads and writes all three within a single transaction per budget, so separating them would require three separate data-store boxes all connected to the same process node.

**Why the recommendations dashboard uses MAX(generated_date) instead of DELETE + INSERT.**
New recommendation rows are inserted with `generated_date = today`. The `GET /recommendations/` endpoint queries `WHERE generated_date = MAX(generated_date)`. This means the previous day's recommendations remain visible to users throughout the generation run; there is no moment where the recommendations list appears empty. This is a deliberate "logical daily replace" pattern.

**Ingestion concurrency guard.**
The `_ingestion_lock` (an `asyncio.Lock`) and `_ingestion_running` boolean prevent overlapping ingestion runs within a single process. This is explicitly a process-local guard — it does not protect against two separate API worker processes running simultaneously. The DFD reflects this by showing P2 as a single process without horizontal scaling notation.

---

## How to Open

1. Go to **[app.diagrams.net](https://app.diagrams.net)**.
2. In the welcome dialog, choose **Open from → Device**.
3. Select `docs/DFD.drawio` from this repository.
4. Use the page tabs at the bottom to switch between **Level 0 - Context** and **Level 1 - DFD**.
