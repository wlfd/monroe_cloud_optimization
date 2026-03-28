# Error Handling Documentation

**CloudCost -- Azure Cloud Cost Optimization SaaS Platform**
CS 701 Course Presentation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Backend Error Handling](#2-backend-error-handling)
3. [External API Error Handling](#3-external-api-error-handling)
4. [Frontend Error Handling](#4-frontend-error-handling)
5. [Background Job Error Handling](#5-background-job-error-handling)
6. [Security-Related Error Handling](#6-security-related-error-handling)
7. [Error Handling Matrix](#7-error-handling-matrix)

---

## 1. Overview

CloudCost adopts a defense-in-depth approach to error handling, applying distinct strategies at each layer of the stack:

- **Fail fast with clear HTTP semantics.** The backend maps every anticipated failure to a specific HTTP status code via custom exception classes. No error silently returns 200.
- **Retry transient failures, fail gracefully on permanent ones.** External API calls (Azure Cost Management, Anthropic Claude, webhooks) use Tenacity-based retry with exponential backoff. When all retries are exhausted, the system falls back to alternative providers or logs the failure and creates an alert.
- **Isolate background job failures.** Scheduler jobs run in isolated contexts. A failure in ingestion does not crash the recommendation pipeline or budget checker. Stale run states are recovered automatically on application restart.
- **Transparent frontend error propagation.** Axios interceptors normalize backend errors and handle token refresh transparently. TanStack Query surfaces loading, error, and retry states to components.
- **Security errors reveal nothing.** Authentication failures always return generic messages ("Invalid email or password") regardless of whether the email exists or the password was wrong, preventing user enumeration.

---

## 2. Backend Error Handling

### 2.1 Custom Exception Classes

All custom exceptions are defined in `backend/app/core/exceptions.py` and extend FastAPI's `HTTPException`:

```python
class CredentialsException(HTTPException):
    # HTTP 401 -- "Could not validate credentials"
    # Includes WWW-Authenticate: Bearer header

class ForbiddenException(HTTPException):
    # HTTP 403 -- default "Forbidden", accepts custom detail

class NotFoundException(HTTPException):
    # HTTP 404 -- default "Not found", accepts custom detail
```

These are raised directly in route handlers and dependency functions. Because they extend `HTTPException`, FastAPI catches them and serializes the response automatically without requiring a custom exception handler.

### 2.2 HTTP Status Code Mapping

| Code | Meaning | Where Used |
|------|---------|------------|
| 401 Unauthorized | Invalid/expired JWT, bad credentials | `CredentialsException`, login failures, refresh token failures |
| 403 Forbidden | Valid auth but insufficient role | `ForbiddenException`, `require_admin` dependency, disabled accounts |
| 404 Not Found | Resource does not exist | `NotFoundException` in route handlers |
| 409 Conflict | Concurrent operation in progress | Ingestion trigger when already running, recommendation trigger when already running |
| 422 Unprocessable Entity | Request body validation failure | Pydantic schema validation (automatic) |
| 429 Too Many Requests | Brute-force lockout active | Login endpoint when account is locked |
| 500 Internal Server Error | Unhandled exception | FastAPI default handler for uncaught exceptions |

### 2.3 FastAPI Dependency Injection Error Handling

The `get_current_user` dependency in `backend/app/core/dependencies.py` validates JWT tokens on every protected route:

```python
async def get_current_user(token, db) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise CredentialsException()
        user_id = payload.get("sub")
        if user_id is None:
            raise CredentialsException()
    except InvalidTokenError:
        raise CredentialsException() from None
    # ... lookup user, check is_active
```

Key patterns:

- **Token type enforcement.** Only tokens with `type: "access"` are accepted; refresh tokens presented as access tokens are rejected.
- **`from None` suppression.** The `raise ... from None` pattern on `InvalidTokenError` prevents the original exception traceback from leaking in debug responses.
- **Inactive user rejection.** Even with a valid JWT, inactive users receive a 401, not a 403, to avoid revealing account existence.

The `require_admin` dependency chains on `get_current_user` and adds an RBAC check:

```python
def require_admin(current_user = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
```

### 2.4 Database Session Management

The `get_db` dependency uses an async context manager to guarantee session cleanup:

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

The `async with` block ensures the session is closed even if the route handler raises an exception. There is no explicit rollback call because SQLAlchemy's async session automatically rolls back uncommitted transactions when the session closes.

### 2.5 Pydantic Validation

All request bodies pass through Pydantic schemas defined in `backend/app/schemas/`. FastAPI automatically returns HTTP 422 with a structured `detail` array when validation fails:

```json
{
  "detail": [
    {
      "loc": ["body", "email"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

No custom validation error handler is required -- this is built into FastAPI's request processing pipeline.

### 2.6 Database Constraint Handling

The ingestion pipeline uses PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` (upsert) to handle duplicate records idempotently rather than raising constraint violation errors:

```python
stmt = pg_insert(BillingRecord).values(rows)
stmt = stmt.on_conflict_do_update(
    index_elements=["usage_date", "subscription_id", "resource_group",
                     "service_name", "meter_category"],
    set_={"pre_tax_cost": stmt.excluded.pre_tax_cost, ...},
)
```

This pattern is applied consistently across ingestion, anomaly detection, and attribution services, converting what would be `IntegrityError` exceptions into no-op updates.

---

## 3. External API Error Handling

### 3.1 Azure Cost Management API

Defined in `backend/app/services/azure_client.py`, the `fetch_with_retry` function wraps Azure API calls with Tenacity retry logic:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_chain(wait_fixed(5), wait_fixed(30), wait_fixed(120)),
    retry=retry_if_exception_type((HttpResponseError, TimeoutError, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def fetch_with_retry(scope, start, end) -> list[dict]:
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max attempts | 3 | Balances recovery with latency budget |
| Wait sequence | 5s, 30s, 120s | Fixed escalating backoff (not exponential) to respect Azure QPU quota (12 QPU/10s) |
| Retried exceptions | `HttpResponseError`, `TimeoutError`, `OSError` | Covers Azure SDK errors, network timeouts, and socket-level failures |
| `before_sleep` | Logs at WARNING level | Provides visibility into retry attempts without flooding logs |
| `reraise` | True | After all retries exhausted, the original exception propagates to the caller |

The synchronous Azure SDK call is wrapped in `asyncio.to_thread()` to avoid blocking the event loop:

```python
rows, column_names, _next_link = await asyncio.to_thread(
    _fetch_page_sync, client, scope, query_def
)
```

**Mock mode:** When `MOCK_AZURE=true`, `fetch_billing_data` returns synthetic records immediately, bypassing all Azure API calls and retry logic entirely. This allows local development and CI testing without credentials.

### 3.2 Anthropic Claude API (LLM Recommendations)

Defined in `backend/app/services/recommendation.py`, the LLM call chain implements a primary-plus-fallback pattern:

**Primary -- Anthropic Claude with retry:**

```python
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type(
        (anthropic.RateLimitError, anthropic.InternalServerError,
         anthropic.APIConnectionError)
    ),
)
async def _call_anthropic(client, resource) -> dict:
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Max attempts | 3 | Limits cost exposure from repeated LLM calls |
| Wait strategy | Exponential backoff, 2s min, 30s max | Respects Anthropic rate limits on 429 responses |
| Retried exceptions | `RateLimitError`, `InternalServerError`, `APIConnectionError` | Transient failures only; `AuthenticationError` and `BadRequestError` are not retried |

**Fallback -- Azure OpenAI:**

If all three Anthropic retries fail, the system falls back to Azure OpenAI:

```python
try:
    result = await _call_anthropic(anthropic_client, resource)
except Exception as exc:
    logger.warning("Anthropic call failed: %s -- trying fallback", exc)
    result = await _call_azure_openai(resource)
```

The Azure OpenAI fallback is a single attempt (no retry decorator). If Azure OpenAI credentials are not configured, `_call_azure_openai` logs a warning and returns `None` gracefully rather than raising.

If both the primary and fallback return `None`, the resource is skipped and processing continues to the next qualifying resource.

**Daily call limit:** A Redis-based counter (`INCR` + `EXPIREAT` at midnight UTC) enforces the `LLM_DAILY_CALL_LIMIT` setting. When the limit is reached, generation stops for remaining resources. Cache hits (24-hour TTL per resource) do not count against this limit.

### 3.3 SMTP and Webhook Delivery

Defined in `backend/app/services/notification.py`:

**Email (SMTP via aiosmtplib):**

- If `SMTP_HOST` is not configured, the send function returns `("failed", "SMTP not configured")` immediately rather than raising.
- SMTP exceptions are caught, logged, and recorded in `NotificationDelivery` with `status="failed"` and the error message stored.
- Email deliveries are not retried by the scheduled retry job.

**Webhook (HTTP POST via httpx):**

- Uses a 10-second timeout on all webhook requests.
- HMAC-SHA256 signature is computed and sent in the `X-CloudCost-Signature` header for payload verification by the receiver.
- Non-2xx responses are recorded as `status="failed"` with the HTTP status code and truncated response body (first 200 characters).
- Network exceptions are caught and recorded with the exception message.

**Retry logic (scheduled job):**

The `retry_failed_deliveries` function runs every 15 minutes via APScheduler. It queries for failed webhook deliveries where `attempt_number < 3` and re-sends each one, creating a new `NotificationDelivery` row with `attempt_number` incremented:

- Maximum 3 total attempts per delivery.
- Only webhook channels are retried (email is excluded).
- Each retry is an independent HTTP POST with fresh HMAC signatures.
- The stored `payload_json` from the original delivery is re-sent, ensuring consistency.

**Channel isolation:** When dispatching to all active channels, each channel delivery is wrapped in its own try/except. A failure on one channel does not prevent delivery to remaining channels.

---

## 4. Frontend Error Handling

### 4.1 Axios Interceptors

Defined in `frontend/src/services/api.ts`, two interceptors manage authentication and error propagation:

**Request interceptor -- token attachment:**

```typescript
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers['Authorization'] = `Bearer ${token}`;
  }
  return config;
});
```

The access token is stored in a module-scoped variable (`_accessToken`), never in `localStorage` or `sessionStorage`, mitigating XSS-based token theft.

**Response interceptor -- automatic token refresh on 401:**

```typescript
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as typeof error.config & { _retry?: boolean };
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh') &&
      !originalRequest.url?.includes('/auth/login')
    ) {
      originalRequest._retry = true;
      try {
        const { data } = await api.post<{ access_token: string }>('/auth/refresh');
        setAccessToken(data.access_token);
        originalRequest.headers!['Authorization'] = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        setAccessToken(null);  // Refresh failed -- clear token
      }
    }
    return Promise.reject(error);
  }
);
```

Key safeguards:

- **Single retry guard.** The `_retry` flag prevents infinite refresh loops.
- **Auth endpoint exclusion.** Requests to `/auth/refresh` and `/auth/login` are never retried, preventing recursive refresh attempts.
- **Graceful degradation.** If the refresh call itself fails, the access token is cleared and the original error propagates to the caller. The consuming component or auth context handles redirection to the login page.

### 4.2 TanStack Query Error States

Frontend data fetching uses TanStack Query hooks (in `frontend/src/services/`). The library provides built-in error handling:

- **Loading states:** `isLoading` / `isPending` flags allow components to show skeleton UIs or spinners.
- **Error states:** `isError` and `error` fields allow components to render error messages.
- **Automatic retry:** TanStack Query retries failed queries up to 3 times with exponential backoff by default before surfacing the error to the component.
- **Background refetching:** Stale data remains visible while a refetch is in progress; the UI only switches to an error state if the refetch also fails.

### 4.3 User-Facing Error Messages

Backend error responses follow a consistent `{"detail": "..."}` structure. The frontend extracts the `detail` field from `AxiosError.response.data` to display user-facing messages. Examples:

| Backend Response | User Sees |
|-----------------|-----------|
| `401: "Invalid email or password"` | Login form error message |
| `429: "Account temporarily locked"` | Lockout notice with implicit wait guidance |
| `403: "Admin role required"` | Access denied message |
| `409: "Ingestion already in progress"` | Status indicator that a job is running |

### 4.4 Network Failure Handling

When the backend is unreachable (no `error.response`), Axios rejects with a network error. TanStack Query treats this as a retryable failure. After retries are exhausted, the component receives an error object without a response body, which is presented as a generic connectivity message.

The `withCredentials: true` configuration on the Axios instance ensures the HttpOnly refresh token cookie is sent with every request, including cross-origin requests during local development.

---

## 5. Background Job Error Handling

### 5.1 APScheduler Job Configuration

The scheduler is configured in `backend/app/core/scheduler.py` with defensive defaults:

```python
scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,           # Collapse missed executions into one
        "max_instances": 1,         # Only one instance of each job at a time
        "misfire_grace_time": 300,  # 5-minute grace period for late jobs
    },
    timezone="UTC",
)
```

- **Coalesce:** If the application was down and multiple scheduled runs were missed, only one execution fires on restart.
- **Max instances:** Prevents overlapping runs of the same job, especially important for the ingestion pipeline.
- **Misfire grace time:** Jobs missed by more than 5 minutes are dropped rather than executing with stale timing assumptions.

Jobs are registered in the `lifespan` function in `backend/app/main.py`. Each job is independent; an exception in one does not affect others.

### 5.2 Ingestion Pipeline Error Handling

The ingestion orchestrator in `backend/app/services/ingestion.py` implements multiple error handling layers:

**Concurrency guard:**

```python
_ingestion_lock = asyncio.Lock()

async def run_ingestion(triggered_by="scheduler"):
    if _ingestion_lock.locked():
        logger.info("Already running -- skipping")
        return
    async with _ingestion_lock:
        await _do_ingestion(triggered_by)
```

If a second ingestion run is triggered (by scheduler or admin API) while one is active, it is silently skipped rather than queued or errored.

**Failure recording and alerting:**

When `_do_ingestion` catches an exception, it opens a separate database session to avoid transaction contamination and records both a failed `IngestionRun` and an `IngestionAlert`:

```python
except Exception as exc:
    async with AsyncSessionLocal() as err_session:
        await log_ingestion_run(err_session, status="failed", error_detail=str(exc), ...)
        alert = await create_ingestion_alert(err_session, error_detail=str(exc), retry_count=3)
        try:
            await notify_ingestion_failed(err_session, ...)
        except Exception as notify_exc:
            logger.error("Notification failed: %s", notify_exc)
    raise
```

Note: the notification dispatch itself is wrapped in a try/except so that a notification failure does not mask the original ingestion failure.

**Non-fatal sub-step failures:**

The attribution step after ingestion is explicitly non-fatal:

```python
try:
    await run_attribution()
except Exception as exc:
    logger.error("Attribution run failed after ingestion: %s", exc)
    # Non-fatal -- does not fail the ingestion run record
```

**Stale run recovery:**

On application startup, `recover_stale_runs` marks any `IngestionRun` rows with `status="running"` as `"interrupted"`:

```python
async def recover_stale_runs(session):
    stmt = update(IngestionRun).where(
        IngestionRun.status == "running"
    ).values(status="interrupted", completed_at=datetime.now(UTC))
```

This prevents stale "running" states from blocking future runs or confusing the admin dashboard after a crash restart.

**Backfill error propagation:**

During the 24-month backfill, each monthly chunk is processed individually. If a chunk fails, the exception propagates immediately (`raise`), halting the backfill. The partial progress is preserved because each chunk's upsert is committed independently.

### 5.3 Notification Retry

The `retry_failed_deliveries` job runs every 15 minutes:

- Queries `NotificationDelivery` rows where `status="failed"` and `attempt_number < 3`.
- Creates a new delivery row for each retry attempt (preserving the audit trail of all attempts).
- After 3 total attempts, the delivery is abandoned (no further retries).
- The job manages its own `AsyncSessionLocal` session since it runs outside request context.

---

## 6. Security-Related Error Handling

### 6.1 Brute-Force Lockout

Implemented in `backend/app/api/v1/auth.py`, the login endpoint tracks failed attempts per user:

```python
if not verify_password(form_data.password, user.password_hash):
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= 5:
        user.locked_until = datetime.now(UTC) + timedelta(minutes=15)
    await db.commit()
    raise HTTPException(status_code=401, detail="Invalid email or password")
```

**Lockout check (before password verification):**

```python
if user.locked_until is not None and user.locked_until > datetime.now(UTC):
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Account temporarily locked",
    )
```

| Parameter | Value |
|-----------|-------|
| Failed attempt threshold | 5 |
| Lockout duration | 15 minutes |
| HTTP status during lockout | 429 Too Many Requests |
| Counter reset | On successful login (`failed_login_attempts = 0`, `locked_until = None`) |

The lockout is checked before password verification to avoid unnecessary bcrypt computation on locked accounts.

### 6.2 JWT Validation Failures

JWT validation occurs in the `get_current_user` dependency and covers:

| Failure Mode | Handling |
|-------------|----------|
| Token expired | `InvalidTokenError` caught, raises `CredentialsException` (401) |
| Token tampered/invalid signature | `InvalidTokenError` caught, raises `CredentialsException` (401) |
| Token type mismatch (refresh token used as access) | Explicit `type` field check, raises `CredentialsException` (401) |
| Missing `sub` claim | Explicit null check, raises `CredentialsException` (401) |
| User deleted or deactivated after token issued | Database lookup returns None or `is_active=False`, raises `CredentialsException` (401) |

All JWT failures return the same 401 response with `"Could not validate credentials"` to prevent information leakage about which validation step failed.

### 6.3 Refresh Token Validation

The `/auth/refresh` endpoint performs additional checks beyond JWT decoding:

- **Token type verification:** Only tokens with `type: "refresh"` are accepted.
- **Session existence:** The hashed token must match a row in `user_sessions`.
- **Revocation check:** Sessions with `revoked=True` are rejected.
- **Expiry check:** Sessions past `expires_at` are rejected.
- **User status:** The associated user must exist and have `is_active=True`.

All failure paths raise the same `401: "Invalid or expired refresh token"` error.

### 6.4 RBAC Authorization Failures

Role-based access control is enforced via FastAPI dependencies:

- `require_admin` -- returns 403 with `"Admin role required"` if the authenticated user's role is not `admin`.
- Route-level role checks can use `ForbiddenException` for custom messages.

The four-role hierarchy (`admin`, `devops`, `finance`, `viewer`) is enforced at the route level, not via middleware, allowing fine-grained per-endpoint authorization.

---

## 7. Error Handling Matrix

| Error Scenario | HTTP Code | User-Facing Message | Recovery Action |
|---------------|-----------|---------------------|-----------------|
| Invalid login credentials | 401 | "Invalid email or password" | Re-enter credentials |
| Expired access token | 401 | (transparent) | Axios interceptor auto-refreshes token and retries |
| Expired/revoked refresh token | 401 | "Invalid or expired refresh token" | Redirect to login page |
| Invalid JWT signature | 401 | "Could not validate credentials" | Redirect to login page |
| Insufficient role | 403 | "Admin role required" / "Forbidden" | Contact administrator |
| Disabled account | 403 | "Account is disabled" | Contact administrator |
| Resource not found | 404 | "Not found" | Navigate away or refresh |
| Concurrent ingestion trigger | 409 | "Ingestion already in progress" | Wait and retry later |
| Concurrent recommendation trigger | 409 | "Recommendation generation already in progress" | Wait and retry later |
| Malformed request body | 422 | Pydantic validation detail array | Fix request fields |
| Account locked (brute force) | 429 | "Account temporarily locked" | Wait 15 minutes |
| Azure API transient failure | -- | (background) | Auto-retry: 3 attempts at 5s/30s/120s intervals |
| Azure API permanent failure | -- | Ingestion alert created | Admin reviews IngestionAlert dashboard |
| Anthropic LLM transient error | -- | (background) | Auto-retry: 3 attempts with exponential backoff (2-30s) |
| Anthropic LLM permanent failure | -- | (background) | Automatic fallback to Azure OpenAI |
| Both LLM providers fail | -- | (background) | Resource skipped; generation continues with next resource |
| LLM daily call limit reached | -- | (background) | Generation stops; resumes next day at 02:00 UTC |
| Webhook delivery failure | -- | (background) | Auto-retry: up to 3 attempts every 15 minutes |
| SMTP not configured | -- | (background) | Logged as warning; email delivery marked failed |
| SMTP send failure | -- | (background) | Logged; delivery marked failed; not retried |
| Database connection failure | 500 | "Internal Server Error" | Automatic reconnection via SQLAlchemy pool |
| Stale ingestion run after crash | -- | (background) | Auto-recovered to "interrupted" status on startup |
| Network failure (frontend) | -- | Generic connectivity error | TanStack Query retries up to 3 times with backoff |

---

*Document prepared for CS 701 -- Software Architecture and Design.*
*Based on CloudCost codebase revision `2ffb2be` (main branch).*
