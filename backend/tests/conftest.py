"""
Shared pytest fixtures for the CloudCost backend test suite.

All database and external service interactions are mocked — no real
PostgreSQL, Redis, or Azure API calls are made.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.core.security import get_password_hash, create_access_token


# ---------------------------------------------------------------------------
# Event loop
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Session-scoped event loop for all async tests."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# Mock DB session
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """AsyncMock that mimics a SQLAlchemy AsyncSession.

    The .execute() return value is set per-test via:
        mock_db_session.execute.return_value = mock_result(...)
    """
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.execute = AsyncMock()
    session.close = AsyncMock()
    return session


def make_scalars_result(items: list):
    """Build a mock execute() return value whose .scalars().all() yields `items`."""
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = items
    scalars_mock.first.return_value = items[0] if items else None
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    result.scalar_one_or_none.return_value = items[0] if items else None
    result.scalar.return_value = items[0] if items else None
    result.all.return_value = items
    result.first.return_value = items[0] if items else None
    return result


def make_scalar_result(value):
    """Build a mock execute() return value whose .scalar() yields `value`."""
    result = MagicMock()
    result.scalar.return_value = value
    result.scalar_one_or_none.return_value = value
    result.scalars.return_value = MagicMock(all=MagicMock(return_value=[value] if value is not None else []))
    return result


# ---------------------------------------------------------------------------
# Mock Redis
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """AsyncMock that mimics a redis.asyncio.Redis client."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expireat = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


# ---------------------------------------------------------------------------
# Mock Azure cost management client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_azure_client() -> MagicMock:
    """MagicMock for the Azure Cost Management fetch helper."""
    client = MagicMock()
    client.fetch_with_retry = AsyncMock(return_value=[])
    return client


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


def _make_user(
    role: str = "viewer",
    email: str | None = None,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    """Build a mock User ORM object."""
    user = MagicMock()
    user.id = user_id or uuid.uuid4()
    user.email = email or f"{role}@example.com"
    user.full_name = f"Test {role.title()}"
    user.role = role
    user.is_active = True
    user.password_hash = get_password_hash("TestPassword1!")
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = None
    user.sessions = []
    return user


@pytest.fixture
def test_user() -> MagicMock:
    """A standard viewer-role user."""
    return _make_user(role="viewer", email="viewer@example.com")


@pytest.fixture
def admin_user() -> MagicMock:
    """An admin-role user."""
    return _make_user(role="admin", email="admin@example.com")


@pytest.fixture
def devops_user() -> MagicMock:
    """A devops-role user."""
    return _make_user(role="devops", email="devops@example.com")


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


def make_access_token(user: MagicMock) -> str:
    """Create a valid access token for the given mock user."""
    return create_access_token({"sub": str(user.id), "role": user.role})


# ---------------------------------------------------------------------------
# Billing record fixtures
# ---------------------------------------------------------------------------


def _make_billing_record(
    *,
    usage_date: date | None = None,
    service_name: str = "Virtual Machines",
    resource_group: str = "rg-prod",
    pre_tax_cost: float = 100.0,
    tag: str = "tenant-a",
    resource_name: str = "vm-01",
    subscription_id: str = "sub-001",
    meter_category: str = "Compute",
) -> MagicMock:
    record = MagicMock()
    record.id = uuid.uuid4()
    record.usage_date = usage_date or date.today()
    record.subscription_id = subscription_id
    record.resource_group = resource_group
    record.service_name = service_name
    record.meter_category = meter_category
    record.region = "eastus"
    record.tag = tag
    record.resource_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{resource_name}"
    record.resource_name = resource_name
    record.pre_tax_cost = Decimal(str(pre_tax_cost))
    record.currency = "USD"
    record.ingested_at = datetime.now(timezone.utc)
    record.updated_at = datetime.now(timezone.utc)
    return record


@pytest.fixture
def test_billing_records() -> list[MagicMock]:
    """A list of realistic billing records spanning the last 3 days."""
    today = date.today()
    records = []
    for i in range(3):
        day = today - timedelta(days=i)
        records.append(_make_billing_record(usage_date=day, pre_tax_cost=200.0 + i * 10))
        records.append(
            _make_billing_record(
                usage_date=day,
                service_name="Storage",
                resource_group="rg-data",
                pre_tax_cost=50.0 + i * 5,
                tag="tenant-b",
                resource_name="storage-01",
            )
        )
    return records


# ---------------------------------------------------------------------------
# Anomaly fixture
# ---------------------------------------------------------------------------


def _make_anomaly(
    *,
    service_name: str = "Virtual Machines",
    resource_group: str = "rg-prod",
    severity: str = "critical",
    status: str = "new",
    expected: bool = False,
    pct_deviation: float = 150.0,
    estimated_monthly_impact: float = 1500.0,
    baseline_daily_avg: float = 100.0,
    current_daily_cost: float = 250.0,
    detected_date: date | None = None,
) -> MagicMock:
    anomaly = MagicMock()
    anomaly.id = uuid.uuid4()
    anomaly.detected_date = detected_date or date.today()
    anomaly.service_name = service_name
    anomaly.resource_group = resource_group
    anomaly.description = f"Spend increased {pct_deviation:.0f}% in {resource_group}"
    anomaly.severity = severity
    anomaly.status = status
    anomaly.expected = expected
    anomaly.pct_deviation = Decimal(str(pct_deviation))
    anomaly.estimated_monthly_impact = Decimal(str(estimated_monthly_impact))
    anomaly.baseline_daily_avg = Decimal(str(baseline_daily_avg))
    anomaly.current_daily_cost = Decimal(str(current_daily_cost))
    anomaly.created_at = datetime.now(timezone.utc)
    anomaly.updated_at = datetime.now(timezone.utc)
    return anomaly


@pytest.fixture
def test_anomaly() -> MagicMock:
    return _make_anomaly()


# ---------------------------------------------------------------------------
# Budget / threshold fixtures
# ---------------------------------------------------------------------------


def _make_budget(
    *,
    name: str = "Monthly Subscription",
    scope_type: str = "subscription",
    scope_value: str | None = None,
    amount_usd: float = 10000.0,
    period: str = "monthly",
    is_active: bool = True,
) -> MagicMock:
    budget = MagicMock()
    budget.id = uuid.uuid4()
    budget.name = name
    budget.scope_type = scope_type
    budget.scope_value = scope_value
    budget.amount_usd = Decimal(str(amount_usd))
    budget.period = period
    budget.start_date = date.today().replace(day=1)
    budget.end_date = None
    budget.is_active = is_active
    budget.created_by = uuid.uuid4()
    budget.created_at = datetime.now(timezone.utc)
    budget.updated_at = datetime.now(timezone.utc)
    return budget


def _make_threshold(
    budget_id: uuid.UUID | None = None,
    threshold_percent: int = 80,
    notification_channel_id: uuid.UUID | None = None,
    last_triggered_period: str | None = None,
) -> MagicMock:
    threshold = MagicMock()
    threshold.id = uuid.uuid4()
    threshold.budget_id = budget_id or uuid.uuid4()
    threshold.threshold_percent = threshold_percent
    threshold.notification_channel_id = notification_channel_id
    threshold.last_triggered_at = None
    threshold.last_triggered_period = last_triggered_period
    return threshold


def _make_notification_channel(
    channel_type: str = "webhook",
    url: str = "https://hooks.example.com/test",
    secret: str = "test-secret",
) -> MagicMock:
    channel = MagicMock()
    channel.id = uuid.uuid4()
    channel.name = f"Test {channel_type}"
    channel.channel_type = channel_type
    if channel_type == "webhook":
        channel.config_json = {"url": url, "secret": secret}
    else:
        channel.config_json = {"address": "ops@example.com"}
    channel.is_active = True
    channel.owner_user_id = None
    channel.created_at = datetime.now(timezone.utc)
    return channel


@pytest.fixture
def test_budget() -> MagicMock:
    return _make_budget()


@pytest.fixture
def test_threshold(test_budget: MagicMock) -> MagicMock:
    return _make_threshold(budget_id=test_budget.id)


@pytest.fixture
def test_channel_webhook() -> MagicMock:
    return _make_notification_channel(channel_type="webhook")


@pytest.fixture
def test_channel_email() -> MagicMock:
    return _make_notification_channel(channel_type="email")


# ---------------------------------------------------------------------------
# FastAPI test client (no real DB — dependencies overridden)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(test_user: MagicMock, admin_user: MagicMock) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client with DB and auth dependencies mocked.

    Provides the app with a mock DB session and a mock current user injected
    via dependency overrides. Individual tests can swap out current_user by
    re-assigning `app.dependency_overrides[get_current_user]`.
    """
    from app.main import app
    from app.core.dependencies import get_db, get_current_user

    async def override_get_db():
        session = AsyncMock()
        session.execute = AsyncMock(return_value=make_scalars_result([]))
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        yield session

    async def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    app.dependency_overrides.clear()
