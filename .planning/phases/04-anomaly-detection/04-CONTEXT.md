# Phase 4: Anomaly Detection - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Automatically surface unusual spending spikes with severity ratings and estimated dollar impact. Users can view, filter, and act on anomalies (dismiss, mark as expected, mark as investigating). Detection runs after each ingestion cycle using a 30-day rolling baseline. Notification/alerting systems and ML model tuning are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Anomaly list placement
- Dedicated **Anomalies page** as a new nav item (after Dashboard, before all others)
- **Summary card on the existing dashboard** showing active anomaly count + worst severity + link to the Anomalies page
- The Anomalies page shows **full browsable history** (not just current period)

### Severity thresholds
- **Both dollar impact AND % deviation from 30-day baseline are required** to flag an anomaly
- Minimum % deviation to flag: **20%+** above baseline (applies to all severity levels)
- Severity tiers by estimated monthly dollar impact:
  - **Critical**: $1,000+ (per ANOMALY-04 requirement)
  - **High**: $500–$999
  - **Medium**: $100–$499
  - Below $100: ignored (not stored, not surfaced — noise)

### Anomaly list and card layout
- **Card-style list**, not a table — each anomaly is a card (reference image provided)
- Top of page: **4 KPI summary cards** — Active Anomalies, Potential Impact ($), Resolved This Month, Detection Accuracy
- Severity summary badges in the section header (e.g. "1 Critical · 1 High · 1 Medium")
- Per card:
  - Colored dot (red = critical, orange = high, blue = medium)
  - Service name, severity badge, status badge (new / investigating / resolved / dismissed)
  - **Generated human-readable description** (e.g. "Spend increased 156% in us-east-1") — backend composes from service, region/resource group, and % deviation
  - Resource group and detected timestamp
  - Estimated Impact shown prominently in red (e.g. "+$4,520")
  - Action buttons: **Investigate**, **View Resources**, **Mark as Expected**, **Dismiss**
- **Detection Configuration panel** at the bottom of the page (read-only display of baseline period, alert threshold, minimum impact) — whether this has an edit UI is Claude's discretion based on phase scope

### Filter UX
- Three dropdown filters above the card list: **Service**, **Resource Group**, **Severity** (All / Critical / High / Medium)
- **Export Report** button in the page header
- Resolved anomalies remain in the list with a resolved badge — filterable by status

### Anomaly lifecycle
- **Status workflow**: New → Investigating → Resolved / Dismissed
- **Auto-resolve**: after each ingestion run, if the anomaly condition is no longer present (spend back to baseline), the system sets status to resolved automatically
- **Manual dismiss**: user can dismiss any anomaly via the Dismiss button at any time
- **Mark as Expected**: sets an `expected` flag on the record and removes it from the active list (records the false positive for reference; no ML tuning needed in this phase) — exact behavior is Claude's discretion
- **Investigate** button: Claude decides whether clicking it transitions status to "Investigating" or simply navigates to a related resource — whichever is more useful

### Claude's Discretion
- Whether the Detection Configuration panel has an editable sensitivity UI or is read-only only
- Exact behavior of the Investigate button (status transition vs. navigation)
- Exact behavior of Mark as Expected beyond setting `expected` flag and removing from active list
- Detection Accuracy KPI calculation approach

</decisions>

<specifics>
## Specific Ideas

- Reference image provided for the Anomalies page layout (card list with KPI row, colored dots, action buttons per card, Detection Configuration panel at bottom)
- The image shows an app called "CloudCost" with a sidebar nav — this matches the existing app shell
- Color coding: red dot/badge for Critical, orange/yellow for High, blue for Medium
- The "Estimated Impact" figure is shown in bold red on the right of each card
- The image shows a "Design Decisions" callout box at the bottom — this is reference context, not a UI element to implement

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-anomaly-detection*
*Context gathered: 2026-02-21*
