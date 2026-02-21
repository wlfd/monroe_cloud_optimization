# Phase 6: Multi-Tenant Attribution - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Tag-based tenant cost mapping: Azure resources are mapped to customer tenants via `tenant_id` resource tags on a daily schedule. Shared and untagged resources are distributed via admin-defined allocation rules. Finance and engineering can view monthly infrastructure cost per tenant (~30 tenants) on a single screen and export it to CSV for Series A unit economics reporting.

Creating posts, tenant alerts, budgeting, and forecasting are out of scope for this phase.

</domain>

<decisions>
## Implementation Decisions

### Tenant Discovery
- Tenants are auto-discovered from distinct `tenant_id` tag values seen in Azure resource data — no pre-registration required
- Admin can optionally assign a human-readable display name to each discovered tenant ID
- When a new `tenant_id` tag appears for the first time, flag it visually in the UI with a "New" badge until admin acknowledges it
- Untagged resources: allocation rules apply first; any cost not covered by a rule appears as a separate "Unallocated" bucket

### Tenant Management (Settings)
- A dedicated Settings/Admin page hosts tenant name management (separate from the attribution view)
- The same Settings page also houses allocation rule management — use tabs or sections to separate the two

### Per-Tenant Attribution View
- Sortable table layout — one row per tenant, dense and scannable
- Each row shows: tenant name/ID, monthly cost ($), % of total spend, month-over-month change ($ or %), top resource category
- Time range defaults to current month; user can navigate back to previous months via a month picker
- Clicking a row expands it inline to show a cost breakdown by service category for that tenant

### Allocation Rule Management
- Rules table with inline Add Rule form (clicking "Add Rule" opens an inline row for input, not a modal)
- A rule can target either a resource group (by name) or a service category (e.g., Compute, Storage) — both target types supported
- When multiple rules match the same resource, first rule wins based on admin-defined priority order
- Rules live on the same Settings page as tenant names

### Claude's Discretion
- Exact column widths, sorting defaults, and table styling
- Badge design and acknowledgement mechanic for new tenants
- How priority ordering is visually managed in the rules table (drag-and-drop vs. numbered input)
- Compression algorithm and temp file handling for CSV export

</decisions>

<specifics>
## Specific Ideas

- The "Unallocated" bucket should appear as its own row in the tenant attribution table so finance can see how much spend hasn't been attributed yet
- The Settings page tenant and rules sections should feel cohesive — admin shouldn't need to navigate between multiple pages to configure attribution

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 06-multi-tenant-attribution*
*Context gathered: 2026-02-21*
