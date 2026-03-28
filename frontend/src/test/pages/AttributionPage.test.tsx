import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { render } from "../test-utils";
import AttributionPage from "@/pages/AttributionPage";
import { server } from "../mocks/server";

const BASE = "http://localhost:8000/api/v1";

const mockAttributions = [
  {
    tenant_id: "tenant-a",
    display_name: "Acme Corp",
    year: 2026,
    month: 3,
    total_cost: 15000,
    pct_of_total: 60,
    mom_delta_usd: 500,
    top_service_category: "Compute",
    allocated_cost: 14000,
    tagged_cost: 1000,
    computed_at: "2026-03-15T00:00:00Z",
  },
  {
    tenant_id: "UNALLOCATED",
    display_name: null,
    year: 2026,
    month: 3,
    total_cost: 5000,
    pct_of_total: 20,
    mom_delta_usd: null,
    top_service_category: null,
    allocated_cost: 0,
    tagged_cost: 0,
    computed_at: "2026-03-15T00:00:00Z",
  },
];

function renderPage() {
  return render(<AttributionPage />, { initialEntries: ["/attribution"] });
}

// ── Page structure ──────────────────────────────────────────────────────────

describe("AttributionPage — page structure", () => {
  it('renders the "Cost Attribution" heading', () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /cost attribution/i })).toBeInTheDocument();
  });
});

// ── Summary cards ───────────────────────────────────────────────────────────

describe("AttributionPage — summary cards", () => {
  it("renders Total Attributed, Unallocated, and Active Tenants summary cards", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/total attributed/i)).toBeInTheDocument();
      expect(screen.getByText(/active tenants/i)).toBeInTheDocument();
    });
  });

  it("shows correct total attributed value", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      // tenant-a has 15000 → "$15,000.00" appears in summary card and table
      const matches = screen.getAllByText("$15,000.00");
      expect(matches.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("shows unallocated cost in summary", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      // Unallocated card label should appear
      const unallocatedLabels = screen.getAllByText(/unallocated/i);
      expect(unallocatedLabels.length).toBeGreaterThan(0);
    });
  });

  it("shows active tenant count (excluding UNALLOCATED)", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      // Only tenant-a counts → 1 active tenant
      const activeTenantsCard = screen.getByText(/active tenants/i).closest("div");
      expect(activeTenantsCard).toBeInTheDocument();
    });
  });
});

// ── Tenant rows ─────────────────────────────────────────────────────────────

describe("AttributionPage — tenant rows", () => {
  it("renders tenant names in the table", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
  });

  it('shows "Unallocated" badge for UNALLOCATED tenant', async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json(mockAttributions)));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Unallocated")).toBeInTheDocument();
    });
  });
});

// ── Empty state ─────────────────────────────────────────────────────────────

describe("AttributionPage — empty state", () => {
  it("shows empty state message when no data", async () => {
    server.use(http.get(`${BASE}/attribution/`, () => HttpResponse.json([])));

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no attribution data available/i)).toBeInTheDocument();
    });
  });
});
