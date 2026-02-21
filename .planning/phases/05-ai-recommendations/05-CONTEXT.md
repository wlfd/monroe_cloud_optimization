# Phase 5: AI Recommendations - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Generate daily LLM-powered cost optimization recommendations and display them in the UI. Each recommendation covers one Azure resource (right-sizing, idle, reserved, or storage category) with a plain-language explanation, estimated monthly savings, and confidence score. Includes Redis caching (24hr TTL) and a configurable daily call limit. This phase is read-only — accepting, dismissing, and tracking realized savings are v2 features.

</domain>

<decisions>
## Implementation Decisions

### Recommendation layout
- Card-based list (expandable rows stacked vertically), matching the reference design
- Each card shows: resource name, category badge, risk/confidence badge, estimated savings/mo, confidence %, current → recommended comparison panel, cost trend data from billing (not CPU/memory — we use Azure billing data, not live metrics), and the LLM explanation inline (always visible, not collapsed)
- Summary stat row at top: Potential Monthly Savings (highlighted), Total Recommendations count, per-category counts (right-sizing, idle, reserved, storage)
- Full filter bar: Type (category), Risk Level, Min Savings, Confidence dropdowns — matching the reference design

### Generation targeting
- All resources with monthly spend above a configurable threshold qualify for an LLM recommendation (default: $50/month)
- Daily run processes resources sorted by current-month spend descending — highest spenders first
- When daily call limit is hit mid-run, the run stops cleanly; highest-spend resources are always covered first
- Daily run **replaces** previous recommendations — users always see today's fresh set, old ones are overwritten

### LLM provider setup
- **Primary:** Anthropic Claude Sonnet 4.6 (note: this overrides AI-01 which specified Azure OpenAI primary — user explicitly chose Anthropic as primary)
- **Configurable:** Model is admin-configurable; Azure OpenAI is available as the fallback provider
- **Fallback trigger:** Claude's discretion — handle sensibly (e.g., retry transient errors, fall back on availability/rate-limit failures)
- **Prompt data per call:** resource name, resource type, resource group, subscription, service category, last 30 days of billed cost
- **Output structure:** JSON via tool use / structured output — forced structured JSON for reliable parsing, not free-text extraction
- **Required fields in output:** category (right-sizing/idle/reserved/storage), plain-language explanation, estimated monthly savings, confidence score (0–100)

### Limit and cache transparency
- When the daily call limit is reached, show a banner on the recommendations page: "Daily recommendation limit reached. New recommendations will generate tomorrow."
- Cache is **invisible to users** — no "Generated: [date]" label or cache indicators on cards
- Admin visibility into LLM usage (calls used today, cache hit rate, active provider): Claude's discretion — decide appropriate level of admin visibility
- **Empty state:** Show an empty state with a manual trigger button for admins — useful for setup, testing, and first-day scenarios before the scheduled job has run

### Claude's Discretion
- Fallback trigger logic (retry policy, error classification, failover threshold)
- Admin LLM usage visibility (whether to surface in Settings or just logs)
- Exact card spacing, typography, and visual polish
- Loading skeleton design
- Error states (LLM API down, Redis unavailable)
- Cost trend visualization format within cards (bar chart, sparkline, or plain numbers)

</decisions>

<specifics>
## Specific Ideas

- User shared a detailed reference UI (CloudCost "Resource Optimization" screenshot): card list with current → recommended comparison panels, category + risk badges, utilization bars (our version replaces these with billing cost trend data), summary stat row, and filter bar
- Cards should feel like that reference — the current/recommended comparison panel with the arrow between them is a key visual element to preserve
- Primary LLM is Anthropic Claude Sonnet 4.6 (not Azure OpenAI as originally specified in AI-01)

</specifics>

<deferred>
## Deferred Ideas

- **Apply Now / Schedule / Dismiss buttons on cards** — v2 scope (AI-05: mark as Accepted, Dismissed, Deferred)
- **Realized savings tracking** — v2 scope (AI-06)
- **"Applied This Month" stat in summary row** — requires v2 acceptance tracking to populate
- **Bulk selection + "Apply Selected"** — v2 scope, requires apply action

</deferred>

---

*Phase: 05-ai-recommendations*
*Context gathered: 2026-02-21*
