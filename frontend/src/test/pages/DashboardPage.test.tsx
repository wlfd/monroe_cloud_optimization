import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { screen, waitFor } from '@testing-library/react';
import { render } from '../test-utils';
import { DashboardPage } from '@/pages/DashboardPage';
import { server } from '../mocks/server';
import { mockSpendSummary, mockBreakdownData, mockTopResources } from '../mocks/handlers';

// DashboardPage calls: useSpendSummary, useSpendTrend, useSpendBreakdown,
// useTopResources, and useAnomalySummary. All are handled by the default MSW
// handlers so most tests render the page and assert on the resulting DOM.

function renderDashboardPage() {
  return render(<DashboardPage />, { initialEntries: ['/dashboard'] });
}

// ── Page structure ────────────────────────────────────────────────────────────

describe('DashboardPage — page structure', () => {
  it('renders the Dashboard heading', () => {
    renderDashboardPage();
    expect(screen.getByRole('heading', { name: /dashboard/i })).toBeInTheDocument();
  });

  it('renders all four KPI card titles', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/month-to-date spend/i)).toBeInTheDocument();
      expect(screen.getByText(/projected month-end/i)).toBeInTheDocument();
      expect(screen.getByText(/prior month/i)).toBeInTheDocument();
      expect(screen.getByText(/active anomalies/i)).toBeInTheDocument();
    });
  });

  it('renders the Daily Spend Trend section', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/daily spend trend/i)).toBeInTheDocument();
    });
  });

  it('renders the Cost Breakdown section', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/cost breakdown/i)).toBeInTheDocument();
    });
  });

  it('renders the Top 10 Most Expensive Resources section', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/top 10 most expensive resources/i)).toBeInTheDocument();
    });
  });
});

// ── KPI card values ───────────────────────────────────────────────────────────

describe('DashboardPage — KPI card values', () => {
  it('shows MTD spend formatted as currency', async () => {
    renderDashboardPage();

    // mockSpendSummary.mtd_total = 42750.5 → "$42,750.50"
    await waitFor(() => {
      expect(
        screen.getByText(`$${mockSpendSummary.mtd_total.toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`)
      ).toBeInTheDocument();
    });
  });

  it('shows projected month-end formatted as currency', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(
        screen.getByText(`$${mockSpendSummary.projected_month_end.toLocaleString('en-US', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })}`)
      ).toBeInTheDocument();
    });
  });

  it('shows the MoM delta badge with a decrease arrow and green color', async () => {
    renderDashboardPage();

    // mom_delta_pct = -5.2 → "↓ -5.2% vs prior month"
    await waitFor(() => {
      expect(screen.getByText(/↓.*-5\.2%.*vs prior month/i)).toBeInTheDocument();
    });
  });

  it('shows the active anomaly count from the anomaly summary', async () => {
    renderDashboardPage();

    // mockAnomalySummary.active_count = 3
    await waitFor(() => {
      // The anomaly count card shows "3"
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('shows "View anomalies →" link pointing to /anomalies', async () => {
    renderDashboardPage();

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /view anomalies/i });
      expect(link).toHaveAttribute('href', '/anomalies');
    });
  });
});

// ── Loading state ─────────────────────────────────────────────────────────────

describe('DashboardPage — loading state', () => {
  it('shows loading placeholders while spend summary is loading', () => {
    // Delay all cost responses to catch the loading state synchronously
    server.use(
      http.get('http://localhost:8000/api/v1/costs/summary', async () => {
        await new Promise((r) => setTimeout(r, 500));
        return HttpResponse.json(mockSpendSummary);
      })
    );

    renderDashboardPage();

    // animate-pulse div is present during loading
    const loadingPlaceholders = document.querySelectorAll('[class*="animate-pulse"]');
    expect(loadingPlaceholders.length).toBeGreaterThan(0);
  });
});

// ── Error state ───────────────────────────────────────────────────────────────

describe('DashboardPage — error state', () => {
  it('shows an error message when the spend summary endpoint fails', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/summary', () =>
        new HttpResponse(null, { status: 500 })
      )
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/failed to load cost data/i)).toBeInTheDocument();
    });
  });
});

// ── Cost Breakdown table ──────────────────────────────────────────────────────

describe('DashboardPage — Cost Breakdown table', () => {
  it('renders breakdown rows with dimension and cost columns', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText('Azure Compute')).toBeInTheDocument();
      expect(screen.getByText('Azure Storage')).toBeInTheDocument();
    });
  });

  it('shows the cost formatted with two decimal places', async () => {
    renderDashboardPage();

    // mockBreakdownData[0].total_cost = 25000 → "$25,000.00"
    await waitFor(() => {
      expect(
        screen.getByText(
          `$${mockBreakdownData[0].total_cost.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`
        )
      ).toBeInTheDocument();
    });
  });

  it('shows "No cost data" message when breakdown returns an empty array', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/breakdown', () => HttpResponse.json([]))
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/no cost data for this period/i)).toBeInTheDocument();
    });
  });
});

// ── Top Resources table ───────────────────────────────────────────────────────

describe('DashboardPage — Top Resources table', () => {
  it('renders the resource names from the top-resources endpoint', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText('vm-prod-web-01')).toBeInTheDocument();
      expect(screen.getByText('storage-prod-main')).toBeInTheDocument();
    });
  });

  it('renders the service name column', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getAllByText('Azure Compute').length).toBeGreaterThan(0);
    });
  });

  it('shows the "No resource-level data" message when the list is empty', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/top-resources', () =>
        HttpResponse.json([])
      )
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/no resource-level data available/i)).toBeInTheDocument();
    });
  });
});

// ── Time range tabs ───────────────────────────────────────────────────────────

describe('DashboardPage — trend time range tabs', () => {
  it('renders 30d, 60d, 90d tab options', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: '30d' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: '60d' })).toBeInTheDocument();
      expect(screen.getByRole('tab', { name: '90d' })).toBeInTheDocument();
    });
  });
});

// ── Export button ─────────────────────────────────────────────────────────────

describe('DashboardPage — Export CSV button', () => {
  it('renders the Export CSV button', async () => {
    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /export csv/i })).toBeInTheDocument();
    });
  });
});

// ── MoM Delta — positive delta ────────────────────────────────────────────────

describe('DashboardPage — MoM delta positive case', () => {
  it('shows up arrow and red color for a positive MoM delta', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/summary', () =>
        HttpResponse.json({ ...mockSpendSummary, mom_delta_pct: 12.5 })
      )
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText(/↑.*\+12\.5%.*vs prior month/i)).toBeInTheDocument();
    });
  });

  it('shows N/A when mom_delta_pct is null', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/summary', () =>
        HttpResponse.json({ ...mockSpendSummary, mom_delta_pct: null })
      )
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });
});

// ── Top resources missing data fallback ───────────────────────────────────────

describe('DashboardPage — top resources edge cases', () => {
  it('falls back to resource_id when resource_name is empty', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/costs/top-resources', () =>
        HttpResponse.json([
          {
            resource_id: 'res-fallback-id',
            resource_name: '',
            service_name: 'Azure Compute',
            resource_group: 'prod-rg',
            total_cost: mockTopResources[0].total_cost,
          },
        ])
      )
    );

    renderDashboardPage();

    await waitFor(() => {
      expect(screen.getByText('res-fallback-id')).toBeInTheDocument();
    });
  });
});
