import { http, HttpResponse } from 'msw';
import type { Anomaly, AnomalySummary } from '@/services/anomaly';
import type { SpendSummary, DailySpend, BreakdownItem, TopResource } from '@/services/cost';
import type { User } from '@/types/auth';

// ── Shared test fixtures ─────────────────────────────────────────────────────

export const mockUser: User = {
  id: 'user-1',
  email: 'admin@example.com',
  full_name: 'Test Admin',
  role: 'admin',
  is_active: true,
};

export const mockAnomalies: Anomaly[] = [
  {
    id: 'anomaly-1',
    detected_date: '2026-03-10',
    service_name: 'Azure Compute',
    resource_group: 'prod-rg',
    description: 'Unusual spike in VM usage detected.',
    severity: 'critical',
    status: 'new',
    expected: false,
    pct_deviation: 45,
    estimated_monthly_impact: 1200,
    baseline_daily_avg: 80,
    current_daily_cost: 116,
    created_at: '2026-03-10T08:00:00Z',
    updated_at: '2026-03-10T08:00:00Z',
  },
  {
    id: 'anomaly-2',
    detected_date: '2026-03-11',
    service_name: 'Azure Storage',
    resource_group: 'dev-rg',
    description: 'Storage egress cost increased.',
    severity: 'high',
    status: 'investigating',
    expected: false,
    pct_deviation: 28,
    estimated_monthly_impact: 600,
    baseline_daily_avg: 30,
    current_daily_cost: 38.4,
    created_at: '2026-03-11T09:00:00Z',
    updated_at: '2026-03-11T09:00:00Z',
  },
  {
    id: 'anomaly-3',
    detected_date: '2026-03-12',
    service_name: 'Azure SQL',
    resource_group: 'prod-rg',
    description: 'Database query costs elevated.',
    severity: 'medium',
    status: 'new',
    expected: false,
    pct_deviation: 22,
    estimated_monthly_impact: 150,
    baseline_daily_avg: 20,
    current_daily_cost: 24.4,
    created_at: '2026-03-12T10:00:00Z',
    updated_at: '2026-03-12T10:00:00Z',
  },
];

export const mockAnomalySummary: AnomalySummary = {
  active_count: 3,
  critical_count: 1,
  high_count: 1,
  medium_count: 1,
  total_potential_impact: 1950,
  resolved_this_month: 2,
  detection_accuracy: 94.5,
};

export const mockSpendSummary: SpendSummary = {
  mtd_total: 42750.5,
  projected_month_end: 58100.25,
  prior_month_total: 55000.0,
  mom_delta_pct: -5.2,
};

export const mockTrendData: DailySpend[] = [
  { usage_date: '2026-02-12', total_cost: 1800 },
  { usage_date: '2026-02-13', total_cost: 1950 },
  { usage_date: '2026-02-14', total_cost: 1750 },
];

export const mockBreakdownData: BreakdownItem[] = [
  { dimension_value: 'Azure Compute', total_cost: 25000 },
  { dimension_value: 'Azure Storage', total_cost: 10000 },
  { dimension_value: 'Azure SQL', total_cost: 7750.5 },
];

export const mockTopResources: TopResource[] = [
  {
    resource_id: 'res-1',
    resource_name: 'vm-prod-web-01',
    service_name: 'Azure Compute',
    resource_group: 'prod-rg',
    total_cost: 8200,
  },
  {
    resource_id: 'res-2',
    resource_name: 'storage-prod-main',
    service_name: 'Azure Storage',
    resource_group: 'prod-rg',
    total_cost: 4100,
  },
];

// ── API Base URL used by the axios instance ──────────────────────────────────
// The axios instance defaults to http://localhost:8000/api/v1 when
// VITE_API_BASE_URL is not set. MSW intercepts at the network level so we
// match against the same origin + prefix.

const BASE = 'http://localhost:8000/api/v1';

// ── Request handlers ─────────────────────────────────────────────────────────

export const handlers = [
  // Auth
  http.get(`${BASE}/auth/me`, () => HttpResponse.json(mockUser)),

  http.post(`${BASE}/auth/login`, () =>
    HttpResponse.json({ access_token: 'mock-access-token' })
  ),

  http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 204 })),

  http.post(`${BASE}/auth/refresh`, () =>
    HttpResponse.json({ access_token: 'mock-refreshed-token' })
  ),

  // Costs
  http.get(`${BASE}/costs/summary`, () => HttpResponse.json(mockSpendSummary)),

  http.get(`${BASE}/costs/trend`, () => HttpResponse.json(mockTrendData)),

  http.get(`${BASE}/costs/breakdown`, () => HttpResponse.json(mockBreakdownData)),

  http.get(`${BASE}/costs/top-resources`, () => HttpResponse.json(mockTopResources)),

  http.get(`${BASE}/costs/export`, () =>
    new HttpResponse('service,cost\nAzure Compute,25000\n', {
      headers: { 'Content-Type': 'text/csv' },
    })
  ),

  // Anomalies
  http.get(`${BASE}/anomalies/`, ({ request }) => {
    const url = new URL(request.url);
    const severity = url.searchParams.get('severity');
    const serviceName = url.searchParams.get('service_name');

    let results = [...mockAnomalies];
    if (severity) results = results.filter((a) => a.severity === severity);
    if (serviceName) results = results.filter((a) => a.service_name === serviceName);

    return HttpResponse.json(results);
  }),

  http.get(`${BASE}/anomalies/summary`, () => HttpResponse.json(mockAnomalySummary)),

  http.patch(`${BASE}/anomalies/:id/status`, async ({ request, params }) => {
    const { status } = (await request.json()) as { status: string };
    const anomaly = mockAnomalies.find((a) => a.id === params['id']);
    if (!anomaly) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json({ ...anomaly, status });
  }),

  http.patch(`${BASE}/anomalies/:id/expected`, async ({ request, params }) => {
    const { expected } = (await request.json()) as { expected: boolean };
    const anomaly = mockAnomalies.find((a) => a.id === params['id']);
    if (!anomaly) return new HttpResponse(null, { status: 404 });
    return HttpResponse.json({ ...anomaly, expected });
  }),

  http.get(`${BASE}/anomalies/export`, () =>
    new HttpResponse('id,severity,service_name\nanomal-1,critical,Azure Compute\n', {
      headers: { 'Content-Type': 'text/csv' },
    })
  ),

  // Recommendations
  http.get(`${BASE}/recommendations/`, () => HttpResponse.json([])),

  http.get(`${BASE}/recommendations/summary`, () =>
    HttpResponse.json({
      total_count: 0,
      potential_monthly_savings: 0,
      by_category: {},
      daily_limit_reached: false,
      calls_used_today: 0,
      daily_call_limit: 100,
    })
  ),

  // Attribution
  http.get(`${BASE}/attribution/`, () => HttpResponse.json([])),

  // Ingestion
  http.get(`${BASE}/ingestion/status`, () => HttpResponse.json({ running: false })),

  http.get(`${BASE}/ingestion/runs`, () => HttpResponse.json([])),

  http.get(`${BASE}/ingestion/alerts`, () => HttpResponse.json([])),

  // Settings
  http.get(`${BASE}/settings/tenants`, () => HttpResponse.json([])),

  http.get(`${BASE}/settings/rules`, () => HttpResponse.json([])),
];
