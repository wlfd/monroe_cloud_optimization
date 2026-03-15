import { type ReactNode } from 'react';
import {
  render as rtlRender,
  type RenderOptions,
  screen,
  waitFor,
  within,
  act,
  fireEvent,
} from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, type MemoryRouterProps } from 'react-router-dom';
import { AuthProvider } from '@/hooks/useAuth';

// ── Query client factory ─────────────────────────────────────────────────────
// Each test gets its own QueryClient so cached data never leaks between tests.
// Retries are disabled so failed requests surface immediately as errors.

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        // staleTime 0 ensures every test starts with a fresh fetch.
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// ── Wrapper component ────────────────────────────────────────────────────────

interface WrapperProps {
  children: ReactNode;
  initialEntries?: MemoryRouterProps['initialEntries'];
}

function AllProviders({ children, initialEntries = ['/'] }: WrapperProps) {
  const queryClient = createTestQueryClient();
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <AuthProvider>{children}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// ── Custom render ────────────────────────────────────────────────────────────
// Wraps RTL's render with all providers so individual tests don't need to
// set up the provider tree manually.

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  initialEntries?: MemoryRouterProps['initialEntries'];
}

export function render(
  ui: ReactNode,
  { initialEntries, ...renderOptions }: CustomRenderOptions = {}
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <AllProviders initialEntries={initialEntries}>{children}</AllProviders>
    );
  }
  return rtlRender(ui, { wrapper: Wrapper, ...renderOptions });
}

// Re-export commonly used RTL utilities so tests only need to import from here.
export { screen, waitFor, within, act, fireEvent };
