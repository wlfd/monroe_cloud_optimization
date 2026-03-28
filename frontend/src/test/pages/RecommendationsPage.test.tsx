import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { render } from "../test-utils";
import RecommendationsPage from "@/pages/RecommendationsPage";
import { server } from "../mocks/server";
import { mockUser } from "../mocks/handlers";

const BASE = "http://localhost:8000/api/v1";

const mockRec = {
  id: "rec-1",
  generated_date: "2026-03-15",
  resource_name: "vm-prod-01",
  resource_group: "prod-rg",
  subscription_id: "sub-1",
  service_name: "Azure Compute",
  meter_category: "Compute",
  category: "right-sizing",
  explanation: "This VM is oversized.",
  estimated_monthly_savings: 500,
  confidence_score: 85,
  current_monthly_cost: 2000,
  created_at: "2026-03-15T00:00:00Z",
};

const mockSummaryWithData = {
  total_count: 1,
  potential_monthly_savings: 500,
  by_category: { "right-sizing": 1, idle: 0, reserved: 0, storage: 0 },
  daily_limit_reached: false,
  calls_used_today: 5,
  daily_call_limit: 100,
};

function renderPage() {
  return render(<RecommendationsPage />, {
    initialEntries: ["/recommendations"],
  });
}

// ── Page structure ──────────────────────────────────────────────────────────

describe("RecommendationsPage — page structure", () => {
  it('renders the "Recommendations" heading', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /recommendations/i })).toBeInTheDocument();
    });
  });
});

// ── Empty state ─────────────────────────────────────────────────────────────

describe("RecommendationsPage — empty state", () => {
  it('shows "No recommendations yet" when no recommendations exist', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no recommendations yet/i)).toBeInTheDocument();
    });
  });

  it('shows "Generate Recommendations" button for admin users', async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /generate recommendations/i })).toBeInTheDocument();
    });
  });
});

// ── Non-admin user ──────────────────────────────────────────────────────────

describe("RecommendationsPage — non-admin", () => {
  it('does not show "Generate Recommendations" button for viewer', async () => {
    server.use(
      http.get(`${BASE}/auth/me`, () => HttpResponse.json({ ...mockUser, role: "viewer" }))
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no recommendations yet/i)).toBeInTheDocument();
    });

    expect(
      screen.queryByRole("button", { name: /generate recommendations/i })
    ).not.toBeInTheDocument();
  });
});

// ── Summary stats ───────────────────────────────────────────────────────────

describe("RecommendationsPage — summary stats", () => {
  it("shows summary stats when summary data is loaded", async () => {
    server.use(
      http.get(`${BASE}/recommendations/summary`, () => HttpResponse.json(mockSummaryWithData)),
      http.get(`${BASE}/recommendations/`, () => HttpResponse.json([mockRec]))
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/potential monthly savings/i)).toBeInTheDocument();
      expect(screen.getByText("$500")).toBeInTheDocument();
    });
  });
});

// ── Recommendation cards ────────────────────────────────────────────────────

describe("RecommendationsPage — recommendation cards", () => {
  it("renders recommendation cards when data exists", async () => {
    server.use(
      http.get(`${BASE}/recommendations/`, () => HttpResponse.json([mockRec])),
      http.get(`${BASE}/recommendations/summary`, () => HttpResponse.json(mockSummaryWithData))
    );

    renderPage();

    await waitFor(
      () => {
        expect(screen.getByText("vm-prod-01")).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    expect(screen.getByText("prod-rg")).toBeInTheDocument();
    expect(screen.getByText("This VM is oversized.")).toBeInTheDocument();
    // Right-Sizing appears in both summary and card badge
    expect(screen.getAllByText(/right-sizing/i).length).toBeGreaterThanOrEqual(1);
  });
});
