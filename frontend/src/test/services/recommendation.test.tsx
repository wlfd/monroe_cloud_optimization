import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import { type ReactNode } from "react";
import { useRecommendations, useRecommendationSummary } from "@/services/recommendation";
import { server } from "../mocks/server";

const BASE = "http://localhost:8000/api/v1";

// ── Wrapper with all providers ──────────────────────────────────────────────

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0 },
      mutations: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <AuthProvider>{children}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

// ── useRecommendations ──────────────────────────────────────────────────────

describe("useRecommendations", () => {
  it("returns empty array from default handler", async () => {
    const { result } = renderHook(() => useRecommendations(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual([]);
  });

  it("returns recommendation data when available", async () => {
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

    server.use(http.get(`${BASE}/recommendations/`, () => HttpResponse.json([mockRec])));

    const { result } = renderHook(() => useRecommendations(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(1);
    expect(result.current.data?.[0].id).toBe("rec-1");
    expect(result.current.data?.[0].resource_name).toBe("vm-prod-01");
  });
});

// ── useRecommendationSummary ────────────────────────────────────────────────

describe("useRecommendationSummary", () => {
  it("returns summary data from default handler", async () => {
    const { result } = renderHook(() => useRecommendationSummary(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.total_count).toBe(0);
    expect(result.current.data?.potential_monthly_savings).toBe(0);
    expect(result.current.data?.daily_limit_reached).toBe(false);
    expect(result.current.data?.daily_call_limit).toBe(100);
  });

  it("returns populated summary when overridden", async () => {
    server.use(
      http.get(`${BASE}/recommendations/summary`, () =>
        HttpResponse.json({
          total_count: 5,
          potential_monthly_savings: 2500,
          by_category: { "right-sizing": 3, idle: 1, reserved: 1, storage: 0 },
          daily_limit_reached: false,
          calls_used_today: 10,
          daily_call_limit: 100,
        })
      )
    );

    const { result } = renderHook(() => useRecommendationSummary(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.total_count).toBe(5);
    expect(result.current.data?.potential_monthly_savings).toBe(2500);
  });
});
