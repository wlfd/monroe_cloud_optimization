import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { render } from '../test-utils';
import AnomaliesPage from '@/pages/AnomaliesPage';
import { server } from '../mocks/server';
import { mockAnomalies, mockAnomalySummary } from '../mocks/handlers';

// AnomaliesPage uses useAnomalies (twice — unfiltered + filtered) and
// useAnomalySummary. The default MSW handlers return mockAnomalies and
// mockAnomalySummary so most tests work without overrides.

function renderAnomaliesPage() {
  return render(<AnomaliesPage />, { initialEntries: ['/anomalies'] });
}

// ── Loading state ─────────────────────────────────────────────────────────────

describe('AnomaliesPage — loading state', () => {
  it('shows skeleton placeholders while the anomalies are loading', () => {
    // Delay the response to keep the page in loading state during the assertion
    server.use(
      http.get('http://localhost:8000/api/v1/anomalies/', async () => {
        await new Promise((r) => setTimeout(r, 200));
        return HttpResponse.json(mockAnomalies);
      })
    );

    renderAnomaliesPage();

    // The Skeleton elements inside the summary cards should be present
    // before the data arrives.  We look for the data-testid that shadcn
    // Skeleton renders ("skeleton") or any animated placeholder.
    const skeletons = document.querySelectorAll('[class*="skeleton"], [class*="animate-pulse"]');
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

// ── Anomaly list rendering ────────────────────────────────────────────────────

describe('AnomaliesPage — anomaly list', () => {
  it('renders a card for each anomaly returned by the API', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      // Each AnomalyCard shows the service_name as a heading
      expect(screen.getByText('Azure Compute')).toBeInTheDocument();
      expect(screen.getByText('Azure Storage')).toBeInTheDocument();
      expect(screen.getByText('Azure SQL')).toBeInTheDocument();
    });
  });

  it('renders the anomaly description text', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      expect(
        screen.getByText('Unusual spike in VM usage detected.')
      ).toBeInTheDocument();
    });
  });

  it('renders severity badges for each anomaly', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      expect(screen.getByText('Critical')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(screen.getByText('Medium')).toBeInTheDocument();
    });
  });

  it('renders the estimated monthly impact for an anomaly', async () => {
    renderAnomaliesPage();

    // anomaly-1 has estimated_monthly_impact: 1200 → formats as +$1,200
    await waitFor(() => {
      expect(screen.getByText('+$1,200')).toBeInTheDocument();
    });
  });

  it('shows the empty state when there are no anomalies', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/anomalies/', () => HttpResponse.json([]))
    );

    renderAnomaliesPage();

    await waitFor(() => {
      expect(
        screen.getByText(/no anomalies detected for the selected filters/i)
      ).toBeInTheDocument();
    });
  });
});

// ── Summary KPI cards ─────────────────────────────────────────────────────────

describe('AnomaliesPage — summary KPI cards', () => {
  it('shows the active anomaly count from the summary endpoint', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      // mockAnomalySummary.active_count = 3
      expect(screen.getByText('3')).toBeInTheDocument();
    });
  });

  it('shows total potential impact formatted as currency', async () => {
    renderAnomaliesPage();

    // mockAnomalySummary.total_potential_impact = 1950
    await waitFor(() => {
      expect(screen.getByText('$1,950')).toBeInTheDocument();
    });
  });

  it('shows the resolved this month count', async () => {
    renderAnomaliesPage();

    // mockAnomalySummary.resolved_this_month = 2
    // Use getAllByText because "2" may appear alongside other single-digit counts.
    await waitFor(() => {
      expect(screen.getAllByText('2').length).toBeGreaterThan(0);
    });
  });

  it('shows detection accuracy as a percentage', async () => {
    renderAnomaliesPage();

    // mockAnomalySummary.detection_accuracy = 94.5
    await waitFor(() => {
      expect(screen.getByText('94.5%')).toBeInTheDocument();
    });
  });

  it('shows N/A for detection accuracy when null', async () => {
    server.use(
      http.get('http://localhost:8000/api/v1/anomalies/summary', () =>
        HttpResponse.json({ ...mockAnomalySummary, detection_accuracy: null })
      )
    );

    renderAnomaliesPage();

    await waitFor(() => {
      expect(screen.getByText('N/A')).toBeInTheDocument();
    });
  });
});

// ── Action buttons ────────────────────────────────────────────────────────────

describe('AnomaliesPage — action buttons', () => {
  it('renders the Investigate button for a "new" anomaly', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      // anomaly-1 is 'new' so it should show the Investigate button
      expect(
        screen.getAllByRole('button', { name: /investigate/i })[0]
      ).toBeInTheDocument();
    });
  });

  it('renders the Dismiss button for a "new" anomaly', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      expect(
        screen.getAllByRole('button', { name: /dismiss/i })[0]
      ).toBeInTheDocument();
    });
  });

  it('renders the Mark as Resolved button for an "investigating" anomaly', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      // anomaly-2 is 'investigating'
      expect(
        screen.getByRole('button', { name: /mark as resolved/i })
      ).toBeInTheDocument();
    });
  });

  it('calls PATCH /anomalies/:id/status when Investigate is clicked', async () => {
    let patchBody: Record<string, unknown> = {};
    let patchId = '';

    server.use(
      http.patch('http://localhost:8000/api/v1/anomalies/:id/status', async ({ request, params }) => {
        patchId = params['id'] as string;
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockAnomalies[0], status: 'investigating' });
      })
    );

    const user = userEvent.setup();
    renderAnomaliesPage();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /investigate/i })[0]).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole('button', { name: /investigate/i })[0]);

    await waitFor(() => {
      expect(patchId).toBe('anomaly-1');
      expect(patchBody['status']).toBe('investigating');
    });
  });

  it('calls PATCH /anomalies/:id/status when Dismiss is clicked', async () => {
    let patchBody: Record<string, unknown> = {};

    server.use(
      http.patch('http://localhost:8000/api/v1/anomalies/:id/status', async ({ request }) => {
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...mockAnomalies[0], status: 'dismissed' });
      })
    );

    const user = userEvent.setup();
    renderAnomaliesPage();

    await waitFor(() => {
      expect(screen.getAllByRole('button', { name: /dismiss/i })[0]).toBeInTheDocument();
    });

    await user.click(screen.getAllByRole('button', { name: /dismiss/i })[0]);

    await waitFor(() => {
      expect(patchBody['status']).toBe('dismissed');
    });
  });
});

// ── Severity filter ───────────────────────────────────────────────────────────

describe('AnomaliesPage — severity filter', () => {
  it('renders the severity select with All Severities as default', async () => {
    renderAnomaliesPage();

    await waitFor(() => {
      // The SelectTrigger shows the placeholder text before a value is chosen
      expect(screen.getByText('All Severities')).toBeInTheDocument();
    });
  });

  // Radix UI Select renders options into a portal that jsdom cannot query via
  // findByRole('option') — the popover relies on layout APIs unavailable in
  // jsdom. This interaction is covered by E2E (Playwright) tests instead.
  it.skip('refetches anomalies filtered by severity when a severity is selected', async () => {
    let lastUrl = '';

    server.use(
      http.get('http://localhost:8000/api/v1/anomalies/', ({ request }) => {
        lastUrl = request.url;
        const url = new URL(request.url);
        const sev = url.searchParams.get('severity');
        return HttpResponse.json(sev ? mockAnomalies.filter((a) => a.severity === sev) : mockAnomalies);
      })
    );

    const user = userEvent.setup({ pointerEventsCheck: 0 });
    renderAnomaliesPage();

    await waitFor(() => {
      expect(screen.getByText('Azure Compute')).toBeInTheDocument();
    });

    const trigger = screen.getByText('All Severities');
    await user.click(trigger);

    const criticalOption = await screen.findByRole('option', { name: /critical/i });
    await user.click(criticalOption);

    await waitFor(() => {
      expect(lastUrl).toContain('severity=critical');
    });
  });
});

// ── Page header ───────────────────────────────────────────────────────────────

describe('AnomaliesPage — page header', () => {
  it('renders the Anomaly Detection heading', async () => {
    renderAnomaliesPage();

    // The heading is present immediately (not data-dependent)
    expect(screen.getByRole('heading', { name: /anomaly detection/i })).toBeInTheDocument();
  });

  it('renders the Export Report button', async () => {
    renderAnomaliesPage();

    expect(screen.getByRole('button', { name: /export report/i })).toBeInTheDocument();
  });
});
