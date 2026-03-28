import { describe, it, expect } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { AuthProvider } from "@/hooks/useAuth";
import { type ReactNode } from "react";
import {
  useSpendSummary,
  useSpendTrend,
  useSpendBreakdown,
  useTopResources,
} from "@/services/cost";
import {
  mockSpendSummary,
  mockTrendData,
  mockBreakdownData,
  mockTopResources,
} from "../mocks/handlers";

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

// ── useSpendSummary ─────────────────────────────────────────────────────────

describe("useSpendSummary", () => {
  it("returns spend summary data after loading", async () => {
    const { result } = renderHook(() => useSpendSummary(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.mtd_total).toBe(mockSpendSummary.mtd_total);
    expect(result.current.data?.projected_month_end).toBe(mockSpendSummary.projected_month_end);
    expect(result.current.data?.prior_month_total).toBe(mockSpendSummary.prior_month_total);
    expect(result.current.data?.mom_delta_pct).toBe(mockSpendSummary.mom_delta_pct);
  });
});

// ── useSpendTrend ───────────────────────────────────────────────────────────

describe("useSpendTrend", () => {
  it("returns daily spend trend data after loading", async () => {
    const { result } = renderHook(() => useSpendTrend(30), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(mockTrendData.length);
    expect(result.current.data?.[0].usage_date).toBe(mockTrendData[0].usage_date);
    expect(result.current.data?.[0].total_cost).toBe(mockTrendData[0].total_cost);
  });
});

// ── useSpendBreakdown ───────────────────────────────────────────────────────

describe("useSpendBreakdown", () => {
  it("returns breakdown data after loading", async () => {
    const { result } = renderHook(() => useSpendBreakdown("service_name", 30), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(mockBreakdownData.length);
    expect(result.current.data?.[0].dimension_value).toBe(mockBreakdownData[0].dimension_value);
    expect(result.current.data?.[0].total_cost).toBe(mockBreakdownData[0].total_cost);
  });
});

// ── useTopResources ─────────────────────────────────────────────────────────

describe("useTopResources", () => {
  it("returns top resources data after loading", async () => {
    const { result } = renderHook(() => useTopResources(30), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(mockTopResources.length);
    expect(result.current.data?.[0].resource_name).toBe(mockTopResources[0].resource_name);
    expect(result.current.data?.[0].total_cost).toBe(mockTopResources[0].total_cost);
  });
});
