import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { renderHook, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { type ReactNode } from 'react';
import { AuthProvider, useAuth } from '@/hooks/useAuth';
import { getAccessToken, setAccessToken } from '@/services/api';
import { server } from '../mocks/server';
import { mockUser } from '../mocks/handlers';

const BASE = 'http://localhost:8000/api/v1';

// ── Wrapper ──────────────────────────────────────────────────────────────────

function makeWrapper(initialPath = '/') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[initialPath]}>
          <AuthProvider>{children}</AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

// ── useAuth basic contract ───────────────────────────────────────────────────

describe('useAuth — session restore on mount', () => {
  it('restores an existing session by calling GET /auth/me', async () => {
    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    // Immediately after mount the hook is loading
    expect(result.current.isLoading).toBe(true);

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.user).toEqual(mockUser);
  });

  it('sets user to null when /auth/me returns 401 (no session)', async () => {
    server.use(
      http.get(`${BASE}/auth/me`, () => new HttpResponse(null, { status: 401 }))
    );

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.user).toBeNull();
  });
});

// ── login ────────────────────────────────────────────────────────────────────

describe('useAuth — login', () => {
  it('stores the access token and populates the user after successful login', async () => {
    setAccessToken(null); // start clean

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });

    // Wait for the initial session restore to finish
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login({ email: 'admin@example.com', password: 'secret' });
    });

    expect(getAccessToken()).toBe('mock-access-token');
    expect(result.current.user).toEqual(mockUser);
  });

  // Run before the rejects.toThrow() test: a thrown act() leaves pending React
  // async work that prevents the next renderHook from completing its initial
  // render — keeping this test earlier in the describe avoids that pollution.
  it('sends credentials as application/x-www-form-urlencoded', async () => {
    setAccessToken(null);

    let contentType: string | null = null;
    let bodyText = '';

    server.use(
      http.post(`${BASE}/auth/login`, async ({ request }) => {
        contentType = request.headers.get('content-type');
        bodyText = await request.text();
        return HttpResponse.json({ access_token: 'tok' });
      })
    );

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.login({ email: 'user@example.com', password: 'pass123' });
    });

    expect(contentType).toContain('application/x-www-form-urlencoded');
    expect(bodyText).toContain('username=user%40example.com');
    expect(bodyText).toContain('password=pass123');
  });

  it('throws when the login endpoint returns 401', async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 }))
    );

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await expect(
      act(async () => {
        await result.current.login({ email: 'bad@example.com', password: 'wrong' });
      })
    ).rejects.toThrow();
  });
});

// ── logout ───────────────────────────────────────────────────────────────────

describe('useAuth — logout', () => {
  it('clears the stored token and sets user to null', async () => {
    setAccessToken('existing-token');

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    await act(async () => {
      await result.current.logout();
    });

    expect(getAccessToken()).toBeNull();
    expect(result.current.user).toBeNull();
  });

  it('clears token even when the /auth/logout endpoint returns an error', async () => {
    setAccessToken('some-token');

    server.use(
      http.post(`${BASE}/auth/logout`, () => new HttpResponse(null, { status: 500 }))
    );

    const { result } = renderHook(() => useAuth(), { wrapper: makeWrapper() });
    await waitFor(() => expect(result.current.isLoading).toBe(false));

    // logout uses try/finally: the server error propagates but the token is
    // still cleared. Catch the error so the test doesn't fail on the throw.
    await act(async () => {
      try {
        await result.current.logout();
      } catch {
        // 500 expected — finally block still cleared the token
      }
    });

    expect(getAccessToken()).toBeNull();
    expect(result.current.user).toBeNull();
  });
});
