"""
Unit tests for FastAPI API routes.

Uses httpx.AsyncClient with the FastAPI app and fully mocked dependencies.
No real database, Redis, or external services are required.

The FastAPI lifespan (Redis + APScheduler) is patched out via a module-level
autouse fixture so no real connections are attempted during tests.

Covers:
- Auth endpoints: POST /auth/login, POST /auth/refresh, GET /auth/me
- Protected route 401 behavior (no token)
- RBAC: viewer cannot trigger ingestion (403), admin can (202)
- Concurrent ingestion guard (409)
- Anomaly endpoints: list, summary, PATCH status (success / invalid / 404)
- Ingestion status endpoint
- Health check (no auth)
"""

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from tests.conftest import (
    _make_anomaly,
    _make_user,
    make_scalar_result,
    make_scalars_result,
    make_access_token,
)


# ---------------------------------------------------------------------------
# No-op lifespan — avoids real Redis and APScheduler startup
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _noop_lifespan(app):
    """Replace the real lifespan with a no-op that skips Redis/scheduler."""
    app.state.redis = AsyncMock()
    yield


# ---------------------------------------------------------------------------
# Module-level autouse fixture — patches lifespan for every test in this file
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def patch_lifespan():
    """Autouse fixture: replaces app lifespan so no real I/O happens on startup."""
    with patch("app.main.lifespan", new=_noop_lifespan):
        yield


# ---------------------------------------------------------------------------
# Helper: build a test AsyncClient with dependency overrides
# ---------------------------------------------------------------------------


def _make_client(
    current_user=None,
    db_execute_results=None,
) -> tuple:
    """Return (app, AsyncClient transport, db_mock) ready for use.

    Callers should use `async with AsyncClient(transport=transport, ...)`.
    """
    from app.main import app

    if current_user is None:
        current_user = _make_user(role="viewer")

    db_mock = AsyncMock()
    if db_execute_results:
        if isinstance(db_execute_results, list):
            db_mock.execute.side_effect = db_execute_results
        else:
            db_mock.execute.return_value = db_execute_results
    else:
        db_mock.execute.return_value = make_scalars_result([])

    db_mock.commit = AsyncMock()
    db_mock.rollback = AsyncMock()
    db_mock.flush = AsyncMock()
    db_mock.refresh = AsyncMock()
    db_mock.add = MagicMock()

    return app, db_mock


# ---------------------------------------------------------------------------
# Auth — POST /api/v1/auth/login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_success():
    """Successful login returns 200 with an access token."""
    from app.main import app
    from app.core.dependencies import get_db
    from app.core.security import get_password_hash

    user = _make_user(role="admin", email="admin@example.com")
    user.password_hash = get_password_hash("AdminPassword1!")

    db_mock = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db_mock.execute.return_value = user_result
    db_mock.commit = AsyncMock()
    db_mock.add = MagicMock()

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@example.com", "password": "AdminPassword1!"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401():
    """Login with wrong password returns 401 Unauthorized."""
    from app.main import app
    from app.core.dependencies import get_db
    from app.core.security import get_password_hash

    user = _make_user(role="viewer")
    user.password_hash = get_password_hash("CorrectPassword1!")

    db_mock = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = user
    db_mock.execute.return_value = user_result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": "WrongPassword"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_user_returns_401():
    """Login with unknown email returns 401 Unauthorized."""
    from app.main import app
    from app.core.dependencies import get_db

    db_mock = AsyncMock()
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = None
    db_mock.execute.return_value = user_result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": "unknown@example.com", "password": "AnyPassword"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user_returns_403():
    """Login for a disabled account returns 403 Forbidden."""
    from app.main import app
    from app.core.dependencies import get_db
    from app.core.security import get_password_hash

    user = _make_user(role="viewer")
    user.is_active = False
    user.password_hash = get_password_hash("Password1!")

    db_mock = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db_mock.execute.return_value = result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": "Password1!"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Auth — GET /api/v1/auth/me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_returns_user_profile():
    """GET /auth/me returns the authenticated user's profile."""
    from app.main import app
    from app.core.dependencies import get_current_user

    user = _make_user(role="admin", email="admin@example.com")
    token = make_access_token(user)

    async def _get_current_user():
        return user

    app.dependency_overrides[get_current_user] = _get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "admin@example.com"
    assert body["role"] == "admin"


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401():
    """GET /auth/me without Bearer token returns 401."""
    from app.main import app
    from app.core.dependencies import get_db

    db_mock = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db_mock.execute.return_value = result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/auth/me")

    app.dependency_overrides.clear()

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Protected routes — 401 without token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("path", [
    "/api/v1/anomalies/",
    "/api/v1/anomalies/summary",
    "/api/v1/ingestion/status",
    "/api/v1/ingestion/runs",
])
async def test_protected_routes_require_token(path: str):
    """Protected routes return 401 when no Authorization header is provided."""
    from app.main import app
    from app.core.dependencies import get_db

    db_mock = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db_mock.execute.return_value = result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(path)

    app.dependency_overrides.clear()

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# RBAC — ingestion endpoint requires admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_ingestion_as_viewer_returns_403():
    """POST /ingestion/run with viewer role returns 403 Forbidden."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    viewer = _make_user(role="viewer")
    token = make_access_token(viewer)

    async def _get_current_user():
        return viewer

    async def _get_db():
        session = AsyncMock()
        session.execute.return_value = make_scalars_result([])
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/ingestion/run",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_trigger_ingestion_as_admin_returns_202():
    """POST /ingestion/run with admin role returns 202 Accepted."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    admin = _make_user(role="admin")
    token = make_access_token(admin)

    async def _get_current_user():
        return admin

    async def _get_db():
        session = AsyncMock()
        session.execute.return_value = make_scalars_result([])
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("app.api.v1.ingestion.is_ingestion_running", return_value=False), \
             patch("app.api.v1.ingestion.asyncio.create_task"):
            response = await client.post(
                "/api/v1/ingestion/run",
                headers={"Authorization": f"Bearer {token}"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


@pytest.mark.asyncio
async def test_trigger_ingestion_already_running_returns_409():
    """POST /ingestion/run returns 409 Conflict when ingestion is already in progress."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    admin = _make_user(role="admin")
    token = make_access_token(admin)

    async def _get_current_user():
        return admin

    async def _get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("app.api.v1.ingestion.is_ingestion_running", return_value=True):
            response = await client.post(
                "/api/v1/ingestion/run",
                headers={"Authorization": f"Bearer {token}"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Anomaly endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_anomalies_returns_200():
    """GET /anomalies/ returns 200 with a list of anomaly objects."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="viewer")
    token = make_access_token(user)
    anomaly = _make_anomaly(severity="critical", status="new")

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = [anomaly]
        result = MagicMock()
        result.scalars.return_value = scalars_mock
        session.execute.return_value = result
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/anomalies/",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["severity"] == "critical"


@pytest.mark.asyncio
async def test_list_anomalies_empty_returns_empty_list():
    """GET /anomalies/ returns empty list when no anomalies exist."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="viewer")
    token = make_access_token(user)

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result = MagicMock()
        result.scalars.return_value = scalars_mock
        session.execute.return_value = result
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/anomalies/",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_anomaly_summary_returns_200():
    """GET /anomalies/summary returns 200 with all expected KPI fields."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="viewer")
    token = make_access_token(user)

    # get_anomaly_summary executes 8 scalar queries in order:
    # active, critical, high, medium, impact, resolved, total_detected, expected
    count_values = [3, 1, 1, 1, 2500.0, 2, 10, 1]
    call_index = [0]

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()

        def make_result(_stmt):
            val = count_values[call_index[0] % len(count_values)]
            call_index[0] += 1
            r = MagicMock()
            r.scalar.return_value = val
            r.scalar_one_or_none.return_value = val
            return r

        session.execute = AsyncMock(side_effect=make_result)
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/anomalies/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert "active_count" in body
    assert "critical_count" in body
    assert "high_count" in body
    assert "medium_count" in body
    assert "total_potential_impact" in body
    assert "resolved_this_month" in body


@pytest.mark.asyncio
async def test_update_anomaly_status_success():
    """PATCH /anomalies/{id}/status returns 200 with updated anomaly."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="admin")
    token = make_access_token(user)
    anomaly = _make_anomaly(status="new")
    anomaly_id = anomaly.id

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = anomaly
        session.execute.return_value = result
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            f"/api/v1/anomalies/{anomaly_id}/status",
            json={"status": "investigating"},
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "investigating"


@pytest.mark.asyncio
async def test_update_anomaly_status_invalid_value_returns_400():
    """PATCH /anomalies/{id}/status returns 400 for invalid status value."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="admin")
    token = make_access_token(user)

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            f"/api/v1/anomalies/{uuid.uuid4()}/status",
            json={"status": "totally_invalid"},
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_update_anomaly_status_not_found_returns_404():
    """PATCH /anomalies/{id}/status returns 404 when anomaly doesn't exist."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    user = _make_user(role="admin")
    token = make_access_token(user)

    async def _get_current_user():
        return user

    async def _get_db():
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute.return_value = result
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.patch(
            f"/api/v1/anomalies/{uuid.uuid4()}/status",
            json={"status": "resolved"},
            headers={"Authorization": f"Bearer {token}"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Ingestion status endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_ingestion_status_returns_running_false():
    """GET /ingestion/status returns running=false when not currently running."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    admin = _make_user(role="admin")
    token = make_access_token(admin)

    async def _get_current_user():
        return admin

    async def _get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("app.api.v1.ingestion.is_ingestion_running", return_value=False):
            response = await client.get(
                "/api/v1/ingestion/status",
                headers={"Authorization": f"Bearer {token}"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["running"] is False


@pytest.mark.asyncio
async def test_get_ingestion_status_returns_running_true():
    """GET /ingestion/status returns running=true when an ingestion is active."""
    from app.main import app
    from app.core.dependencies import get_current_user, get_db

    admin = _make_user(role="admin")
    token = make_access_token(admin)

    async def _get_current_user():
        return admin

    async def _get_db():
        session = AsyncMock()
        yield session

    app.dependency_overrides[get_current_user] = _get_current_user
    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        with patch("app.api.v1.ingestion.is_ingestion_running", return_value=True):
            response = await client.get(
                "/api/v1/ingestion/status",
                headers={"Authorization": f"Bearer {token}"},
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["running"] is True


# ---------------------------------------------------------------------------
# Health check (no auth required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_returns_200():
    """GET /health returns 200 without authentication."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Auth — POST /api/v1/auth/refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_token_no_cookie_returns_401():
    """POST /auth/refresh without a refresh_token cookie returns 401."""
    from app.main import app
    from app.core.dependencies import get_db

    db_mock = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db_mock.execute.return_value = result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/v1/auth/refresh")

    app.dependency_overrides.clear()

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_invalid_cookie_returns_401():
    """POST /auth/refresh with a malformed refresh_token cookie returns 401."""
    from app.main import app
    from app.core.dependencies import get_db

    db_mock = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db_mock.execute.return_value = result

    async def _get_db():
        yield db_mock

    app.dependency_overrides[get_db] = _get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": "not.a.valid.jwt"},
        )

    app.dependency_overrides.clear()

    assert response.status_code == 401
