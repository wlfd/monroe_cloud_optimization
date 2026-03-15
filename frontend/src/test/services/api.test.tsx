import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import api, { getAccessToken, setAccessToken } from '@/services/api';
import { server } from '../mocks/server';

// The axios instance uses http://localhost:8000/api/v1 as its base URL in test.
const BASE = 'http://localhost:8000/api/v1';

// ── Helpers ──────────────────────────────────────────────────────────────────

function capturedHeaders(headers: Record<string, string>) {
  return headers;
}

// ── Tests ────────────────────────────────────────────────────────────────────

describe('api — Axios instance configuration', () => {
  it('sets baseURL to VITE_API_BASE_URL or localhost fallback', () => {
    // The defaults object on the axios instance exposes baseURL.
    expect(api.defaults.baseURL).toBe('http://localhost:8000/api/v1');
  });

  it('sends withCredentials: true so the refresh cookie is included', () => {
    expect(api.defaults.withCredentials).toBe(true);
  });
});

describe('api — request interceptor (JWT injection)', () => {
  beforeEach(() => setAccessToken(null));
  afterEach(() => setAccessToken(null));

  it('does NOT add Authorization header when no token is stored', async () => {
    let receivedHeaders: Record<string, string> = {};

    server.use(
      http.get(`${BASE}/auth/me`, ({ request }) => {
        // Headers are lower-cased by the browser Fetch / msw internals
        request.headers.forEach((value, key) => {
          receivedHeaders = capturedHeaders({ ...receivedHeaders, [key]: value });
        });
        return HttpResponse.json({ id: '1', email: 'a@b.com', full_name: null, role: 'viewer', is_active: true });
      })
    );

    await api.get('/auth/me');

    expect(receivedHeaders['authorization']).toBeUndefined();
  });

  it('attaches Bearer token to requests when a token is stored', async () => {
    setAccessToken('test-jwt-token');

    let authHeader: string | undefined;

    server.use(
      http.get(`${BASE}/auth/me`, ({ request }) => {
        authHeader = request.headers.get('authorization') ?? undefined;
        return HttpResponse.json({ id: '1', email: 'a@b.com', full_name: null, role: 'viewer', is_active: true });
      })
    );

    await api.get('/auth/me');

    expect(authHeader).toBe('Bearer test-jwt-token');
  });
});

describe('api — response interceptor (401 → refresh → retry)', () => {
  beforeEach(() => setAccessToken('expired-token'));
  afterEach(() => setAccessToken(null));

  it('attempts token refresh on a 401 response', async () => {
    let refreshCalled = false;

    server.use(
      // First call to /auth/me returns 401 to simulate an expired token
      http.get(`${BASE}/auth/me`, () => {
        if (!refreshCalled) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json({ id: '1', email: 'a@b.com', full_name: null, role: 'admin', is_active: true });
      }),
      http.post(`${BASE}/auth/refresh`, () => {
        refreshCalled = true;
        return HttpResponse.json({ access_token: 'new-token' });
      })
    );

    const response = await api.get('/auth/me');

    expect(refreshCalled).toBe(true);
    expect(response.data.role).toBe('admin');
  });

  it('stores the new access token after a successful refresh', async () => {
    server.use(
      http.get(`${BASE}/auth/me`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${BASE}/auth/refresh`, () =>
        HttpResponse.json({ access_token: 'brand-new-token' })
      )
    );

    // The retry will also get a 401 (no second override) — that's fine for this
    // test; we only care that setAccessToken was called with the new value.
    try {
      await api.get('/auth/me');
    } catch {
      // Swallow — the retry itself 401s because MSW resets to one call
    }

    // getAccessToken should reflect what was stored during the refresh flow
    expect(getAccessToken()).toBe('brand-new-token');
  });

  it('clears the stored token when the refresh request itself fails', async () => {
    server.use(
      http.get(`${BASE}/auth/me`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${BASE}/auth/refresh`, () => new HttpResponse(null, { status: 401 }))
    );

    await expect(api.get('/auth/me')).rejects.toThrow();

    expect(getAccessToken()).toBeNull();
  });

  it('does NOT retry when the 401 comes from the /auth/login endpoint', async () => {
    let refreshCalled = false;

    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 })),
      http.post(`${BASE}/auth/refresh`, () => {
        refreshCalled = true;
        return HttpResponse.json({ access_token: 'should-not-reach' });
      })
    );

    await expect(
      api.post('/auth/login', new URLSearchParams({ username: 'bad', password: 'bad' }))
    ).rejects.toThrow();

    expect(refreshCalled).toBe(false);
  });
});
