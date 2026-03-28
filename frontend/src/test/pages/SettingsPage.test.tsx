import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "../test-utils";
import SettingsPage from "@/pages/SettingsPage";
import { server } from "../mocks/server";

const BASE = "http://localhost:8000/api/v1";

function renderPage() {
  return render(<SettingsPage />, { initialEntries: ["/settings"] });
}

// ── Page structure ──────────────────────────────────────────────────────────

describe("SettingsPage — page structure", () => {
  it('renders the "Settings" heading', () => {
    renderPage();
    expect(screen.getByRole("heading", { name: /settings/i })).toBeInTheDocument();
  });

  it("renders Tenants and Allocation Rules tabs", () => {
    renderPage();
    expect(screen.getByRole("tab", { name: /tenants/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /allocation rules/i })).toBeInTheDocument();
  });
});

// ── Empty states ────────────────────────────────────────────────────────────

describe("SettingsPage — empty state", () => {
  it("shows empty state for tenants when no data", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText(/no tenant profiles found/i)).toBeInTheDocument();
    });
  });

  it("shows empty state for rules when no data", async () => {
    const user = userEvent.setup();
    renderPage();

    // Wait for tenants tab to finish loading first
    await waitFor(() => {
      expect(screen.getByText(/no tenant profiles found/i)).toBeInTheDocument();
    });

    // Click the Allocation Rules tab using userEvent (required for Radix tabs)
    await user.click(screen.getByRole("tab", { name: /allocation rules/i }));

    await waitFor(() => {
      expect(screen.getByText(/no allocation rules defined/i)).toBeInTheDocument();
    });
  });
});

// ── With tenant data ────────────────────────────────────────────────────────

describe("SettingsPage — with data", () => {
  it("renders tenant data when available", async () => {
    server.use(
      http.get(`${BASE}/settings/tenants`, () =>
        HttpResponse.json([
          {
            id: "tp-1",
            tenant_id: "tenant-a",
            display_name: "Acme Corp",
            first_seen: "2026-01-15T00:00:00Z",
            is_new: false,
          },
        ])
      )
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("tenant-a")).toBeInTheDocument();
      expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    });
  });
});
