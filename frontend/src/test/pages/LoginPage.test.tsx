import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import userEvent from '@testing-library/user-event';
import { screen, waitFor } from '@testing-library/react';
import { render } from '../test-utils';
import { LoginPage } from '@/pages/LoginPage';
import { server } from '../mocks/server';
import { mockUser } from '../mocks/handlers';

const BASE = 'http://localhost:8000/api/v1';

// LoginPage must be rendered inside the auth + router context provided by
// render() from test-utils so that useAuth and useNavigate work correctly.
// We use initialEntries=['/login'] to match the route the page lives on.

function renderLoginPage() {
  return render(<LoginPage />, { initialEntries: ['/login'] });
}

// ── Form rendering ────────────────────────────────────────────────────────────

describe('LoginPage — form rendering', () => {
  it('renders the email input', async () => {
    renderLoginPage();
    // The AuthProvider makes a /auth/me call that returns 401 (no session)
    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });
  });

  it('renders the password input', async () => {
    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });
  });

  it('renders the Sign in button', async () => {
    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
    });
  });

  it('renders the CloudCost card heading', async () => {
    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByText('CloudCost')).toBeInTheDocument();
    });
  });
});

// ── Password visibility toggle ────────────────────────────────────────────────

describe('LoginPage — password visibility toggle', () => {
  it('starts with password field masked', async () => {
    renderLoginPage();
    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password');
    });
  });

  it('shows password when the eye button is clicked', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: /show password/i }));

    expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'text');
  });

  it('hides password when the eye button is clicked a second time', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    const toggle = screen.getByRole('button', { name: /show password/i });
    await user.click(toggle);
    await user.click(screen.getByRole('button', { name: /hide password/i }));

    expect(screen.getByLabelText(/password/i)).toHaveAttribute('type', 'password');
  });
});

// ── Successful login ──────────────────────────────────────────────────────────

describe('LoginPage — successful login', () => {
  it('calls the login endpoint and shows loading state during submission', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
    await user.type(screen.getByLabelText(/password/i), 'secret');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // Button shows loading text while the request is in flight
    expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();
  });

  it('calls the API to fetch the user profile after a successful login', async () => {
    // Verify that the full login flow runs: POST /auth/login → setAccessToken
    // → GET /auth/me to populate the user profile.  We do this by tracking
    // how many times /auth/me is called.
    let meCalls = 0;
    server.use(
      http.get(`${BASE}/auth/me`, () => {
        meCalls++;
        return HttpResponse.json(mockUser);
      })
    );

    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
    await user.type(screen.getByLabelText(/password/i), 'secret');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // Wait for the login flow to complete (loading state clears, no error shown)
    await waitFor(() => {
      expect(screen.queryByText(/invalid email or password/i)).not.toBeInTheDocument();
    });

    // /auth/me should have been called at least twice:
    // once on AuthProvider mount (session restore) and once after login.
    await waitFor(() => {
      expect(meCalls).toBeGreaterThanOrEqual(2);
    });
  });
});

// ── Failed login ──────────────────────────────────────────────────────────────

describe('LoginPage — failed login', () => {
  it('shows an error message when login returns 401', async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 }))
    );

    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'bad@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrongpass');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/invalid email or password/i)
      ).toBeInTheDocument();
    });
  });

  it('re-enables the submit button after a failed login', async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 }))
    );

    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'bad@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled();
    });
  });

  it('does not navigate away on a failed login', async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 }))
    );

    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'bad@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });

    // Login form is still visible
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });
});

// ── Form state management ─────────────────────────────────────────────────────

describe('LoginPage — form field state', () => {
  it('updates email field value as the user types', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/email/i), 'test@example.com');
    expect(screen.getByLabelText(/email/i)).toHaveValue('test@example.com');
  });

  it('updates password field value as the user types', async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText(/password/i), 'mypassword');
    expect(screen.getByLabelText(/password/i)).toHaveValue('mypassword');
  });

  it('clears the error message when the user starts a new login attempt', async () => {
    server.use(
      http.post(`${BASE}/auth/login`, () => new HttpResponse(null, { status: 401 }))
    );

    const user = userEvent.setup();
    renderLoginPage();

    await waitFor(() => {
      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    });

    // First (failed) attempt
    await user.type(screen.getByLabelText(/email/i), 'bad@example.com');
    await user.type(screen.getByLabelText(/password/i), 'wrong');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });

    // Second attempt — error should be cleared at the start of handleSubmit
    // Restore the handler to return success this time
    server.resetHandlers();
    server.use(
      http.get(`${BASE}/auth/me`, () => HttpResponse.json(mockUser)),
      http.post(`${BASE}/auth/login`, () =>
        HttpResponse.json({ access_token: 'good-token' })
      )
    );

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    // The error message should have disappeared
    await waitFor(() => {
      expect(screen.queryByText(/invalid email or password/i)).not.toBeInTheDocument();
    });
  });
});
