import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { type ReactNode } from "react";
import { useAnomalies, useAnomalySummary, useUpdateAnomalyStatus } from "@/services/anomaly";
import { mockAnomalies, mockAnomalySummary } from "../mocks/handlers";

const BASE = "http://localhost:8000/api/v1";

// ── Wrapper providing a fresh QueryClient per test ───────────────────────────

function makeWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

// ── useAnomalies ─────────────────────────────────────────────────────────────

describe("useAnomalies", () => {
  it("fetches the full anomaly list from GET /anomalies/", async () => {
    const { result } = renderHook(() => useAnomalies(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toHaveLength(mockAnomalies.length);
    expect(result.current.data?.[0].id).toBe("anomaly-1");
  });

  it("passes severity filter as a query param to the endpoint", async () => {
    let capturedUrl = "";

    server.use(
      http.get(`${BASE}/anomalies/`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockAnomalies.filter((a) => a.severity === "critical"));
      })
    );

    const { result } = renderHook(() => useAnomalies({ severity: "critical" }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedUrl).toContain("severity=critical");
    expect(result.current.data?.every((a) => a.severity === "critical")).toBe(true);
  });

  it("passes service_name filter as a query param", async () => {
    let capturedUrl = "";

    server.use(
      http.get(`${BASE}/anomalies/`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockAnomalies.filter((a) => a.service_name === "Azure Storage"));
      })
    );

    const { result } = renderHook(() => useAnomalies({ service_name: "Azure Storage" }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedUrl).toContain("service_name=Azure+Storage");
    expect(result.current.data?.[0].service_name).toBe("Azure Storage");
  });

  it('omits filter params when value is "all"', async () => {
    let capturedUrl = "";

    server.use(
      http.get(`${BASE}/anomalies/`, ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json(mockAnomalies);
      })
    );

    const { result } = renderHook(() => useAnomalies({ severity: "all" }), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(capturedUrl).not.toContain("severity=");
  });

  it("transitions to error state when the endpoint returns 500", async () => {
    server.use(http.get(`${BASE}/anomalies/`, () => new HttpResponse(null, { status: 500 })));

    const { result } = renderHook(() => useAnomalies(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

// ── useAnomalySummary ────────────────────────────────────────────────────────

describe("useAnomalySummary", () => {
  it("fetches summary from GET /anomalies/summary", async () => {
    const { result } = renderHook(() => useAnomalySummary(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.active_count).toBe(mockAnomalySummary.active_count);
    expect(result.current.data?.critical_count).toBe(mockAnomalySummary.critical_count);
    expect(result.current.data?.total_potential_impact).toBe(
      mockAnomalySummary.total_potential_impact
    );
  });
});

// ── useUpdateAnomalyStatus ───────────────────────────────────────────────────

describe("useUpdateAnomalyStatus", () => {
  it("sends PATCH /anomalies/:id/status with the new status value", async () => {
    let patchBody: unknown;
    let patchedId = "";

    server.use(
      http.patch(`${BASE}/anomalies/:id/status`, async ({ request, params }) => {
        patchedId = params["id"] as string;
        patchBody = await request.json();
        return HttpResponse.json({ ...mockAnomalies[0], status: "investigating" });
      })
    );

    const { result } = renderHook(() => useUpdateAnomalyStatus(), {
      wrapper: makeWrapper(),
    });

    result.current.mutate({ id: "anomaly-1", status: "investigating" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(patchedId).toBe("anomaly-1");
    expect(patchBody).toEqual({ status: "investigating" });
  });
});
