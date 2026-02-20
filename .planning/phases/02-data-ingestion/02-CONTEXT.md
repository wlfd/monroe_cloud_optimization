# Phase 2: Data Ingestion - Context

**Gathered:** 2026-02-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Azure billing data flows into the database reliably on schedule, with backfill for historical analysis. This phase is the backend pipeline — no end-user UI, but admins need visibility and control. Dashboards, anomaly detection, and AI recommendations are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Manual Controls
- Admins have a "Run now" button to trigger an ingestion run immediately without waiting for the schedule
- Manual run uses the same data window as the scheduled run (no custom date range selection in this phase)
- Show running/idle status so admins know if a run is already in progress before triggering
- Block new triggers while a run is already in progress — one run at a time only (no queuing)

### Error Alerting Format
- When ingestion fails after all retries, show a persistent in-app notification banner visible when admin logs in
- Alert auto-clear behavior: Claude's discretion (e.g., auto-clear on next successful run)
- Alert must include: error message from Azure API, retry count attempted, and failure timestamp
- Maintain a run history log that admins can browse: each run shows timestamp, status (success/fail), records ingested, and any error details

### Data Freshness Window
- Each scheduled run fetches delta only — from the last successful run's end timestamp to now
- Late-arriving Azure records (24-48hr delay): Claude's discretion on whether to include a small re-check window
- If runs are missed (app downtime), the next run catches up from the last successful run
- Maximum catch-up window is capped at 7 days — beyond that, manual backfill is required to avoid large unintended re-ingestion

### Claude's Discretion
- Auto-clear behavior for the in-app failure alert (auto-clear vs persist-until-dismissed)
- Whether to include a 24-48hr re-check window on each run to catch late-arriving Azure records
- Exact retry backoff parameters (beyond the roadmap's "exponential backoff" spec)
- Scheduler implementation (APScheduler, Celery, cron-based, etc.)

</decisions>

<specifics>
## Specific Ideas

- No specific references mentioned — open to standard approaches
- The "Run now" button and run status indicator should live in an admin area (likely alongside the run history log)

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-data-ingestion*
*Context gathered: 2026-02-20*
