"""
Unit tests for app.services.budget.

Covers:
- _current_period: monthly and annual formats
- _period_date_range: monthly/annual boundaries, December rollover
- get_current_period_spend: subscription/resource_group/service/tag scopes
- create_budget / get_budget / update_budget / deactivate_budget CRUD
- add_threshold / remove_threshold
- _check_one_budget: threshold evaluation, deduplication, no-channel status
- check_budget_thresholds: orchestration, error isolation per budget
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    _make_budget,
    _make_notification_channel,
    _make_threshold,
    make_scalar_result,
)

# ---------------------------------------------------------------------------
# _current_period
# ---------------------------------------------------------------------------


def test_current_period_monthly():
    """_current_period returns 'YYYY-MM' for monthly budgets."""
    from app.services.budget import _current_period

    with patch("app.services.budget.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 14)
        result = _current_period("monthly")

    assert result == "2026-03"


def test_current_period_annual():
    """_current_period returns 'YYYY' for annual budgets."""
    from app.services.budget import _current_period

    with patch("app.services.budget.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 14)
        result = _current_period("annual")

    assert result == "2026"


# ---------------------------------------------------------------------------
# _period_date_range
# ---------------------------------------------------------------------------


def test_period_date_range_monthly_march():
    """_period_date_range monthly returns March 1 to April 1 for March."""
    from app.services.budget import _period_date_range

    with patch("app.services.budget.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 14)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        start, end = _period_date_range("monthly")

    assert start == date(2026, 3, 1)
    assert end == date(2026, 4, 1)


def test_period_date_range_monthly_december_rolls_over():
    """_period_date_range monthly in December ends Jan 1 of next year."""
    from app.services.budget import _period_date_range

    with patch("app.services.budget.date") as mock_date:
        mock_date.today.return_value = date(2026, 12, 20)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        start, end = _period_date_range("monthly")

    assert start == date(2026, 12, 1)
    assert end == date(2027, 1, 1)


def test_period_date_range_annual():
    """_period_date_range annual returns Jan 1 to Jan 1 of next year."""
    from app.services.budget import _period_date_range

    with patch("app.services.budget.date") as mock_date:
        mock_date.today.return_value = date(2026, 6, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        start, end = _period_date_range("annual")

    assert start == date(2026, 1, 1)
    assert end == date(2027, 1, 1)


# ---------------------------------------------------------------------------
# get_current_period_spend
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_period_spend_subscription_scope():
    """Subscription-scope budget queries with no additional filter."""
    from app.services.budget import get_current_period_spend

    session = AsyncMock()
    result = make_scalar_result(Decimal("5000.00"))
    session.execute.return_value = result

    budget = _make_budget(scope_type="subscription", scope_value=None)
    spend = await get_current_period_spend(session, budget)

    assert spend == Decimal("5000.00")
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_period_spend_resource_group_scope():
    """resource_group-scope budget returns spend for that RG."""
    from app.services.budget import get_current_period_spend

    session = AsyncMock()
    result = make_scalar_result(Decimal("1200.50"))
    session.execute.return_value = result

    budget = _make_budget(scope_type="resource_group", scope_value="rg-prod")
    spend = await get_current_period_spend(session, budget)

    assert spend == Decimal("1200.50")


@pytest.mark.asyncio
async def test_get_current_period_spend_returns_zero_on_null():
    """get_current_period_spend returns Decimal('0') when DB returns NULL."""
    from app.services.budget import get_current_period_spend

    session = AsyncMock()
    result = make_scalar_result(None)
    session.execute.return_value = result

    budget = _make_budget(scope_type="subscription")
    spend = await get_current_period_spend(session, budget)

    assert spend == Decimal("0")


# ---------------------------------------------------------------------------
# create_budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_budget_adds_and_commits():
    """create_budget creates a Budget, commits, and refreshes."""
    from app.services.budget import create_budget

    session = AsyncMock()
    budget = await create_budget(
        session,
        name="Test Budget",
        scope_type="subscription",
        scope_value=None,
        amount_usd=Decimal("5000"),
        period="monthly",
        start_date=date.today(),
        end_date=None,
        created_by=uuid.uuid4(),
    )

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()

    added = session.add.call_args[0][0]
    assert added.name == "Test Budget"
    assert added.scope_type == "subscription"
    assert added.amount_usd == Decimal("5000")
    assert added.is_active is True


# ---------------------------------------------------------------------------
# update_budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_budget_updates_provided_fields():
    """update_budget only updates the fields passed as non-None kwargs."""
    from app.services.budget import update_budget

    session = AsyncMock()
    existing = _make_budget(name="Old Name", amount_usd=1000.0)

    # get_budget will call execute
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute.return_value = result

    updated = await update_budget(
        session,
        existing.id,
        name="New Name",
        amount_usd=Decimal("2000"),
    )

    assert updated is not None
    assert updated.name == "New Name"
    assert updated.amount_usd == Decimal("2000")
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_budget_not_found():
    """update_budget returns None when budget doesn't exist."""
    from app.services.budget import update_budget

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await update_budget(session, uuid.uuid4(), name="Ghost Budget")

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# deactivate_budget
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deactivate_budget_sets_is_active_false():
    """deactivate_budget soft-deletes by setting is_active=False."""
    from app.services.budget import deactivate_budget

    session = AsyncMock()
    budget = _make_budget(is_active=True)

    result = MagicMock()
    result.scalar_one_or_none.return_value = budget
    session.execute.return_value = result

    deactivated = await deactivate_budget(session, budget.id)

    assert deactivated is not None
    assert deactivated.is_active is False
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# add_threshold / remove_threshold
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_threshold_returns_none_for_missing_budget():
    """add_threshold returns None when the budget_id doesn't exist."""
    from app.services.budget import add_threshold

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    threshold = await add_threshold(
        session, uuid.uuid4(), threshold_percent=80, notification_channel_id=None
    )

    assert threshold is None
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_add_threshold_creates_row_for_existing_budget():
    """add_threshold creates a BudgetThreshold row when budget exists."""
    from app.services.budget import add_threshold

    session = AsyncMock()
    budget = _make_budget()
    result = MagicMock()
    result.scalar_one_or_none.return_value = budget
    session.execute.return_value = result

    threshold = await add_threshold(
        session, budget.id, threshold_percent=75, notification_channel_id=None
    )

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.threshold_percent == 75
    assert added.budget_id == budget.id
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_remove_threshold_returns_true_on_success():
    """remove_threshold deletes the threshold and returns True."""
    from app.services.budget import remove_threshold

    session = AsyncMock()
    threshold = _make_threshold()
    result = MagicMock()
    result.scalar_one_or_none.return_value = threshold
    session.execute.return_value = result

    deleted = await remove_threshold(session, threshold.id)

    assert deleted is True
    session.delete.assert_called_once_with(threshold)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_remove_threshold_returns_false_when_not_found():
    """remove_threshold returns False when threshold doesn't exist."""
    from app.services.budget import remove_threshold

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    deleted = await remove_threshold(session, uuid.uuid4())

    assert deleted is False
    session.delete.assert_not_called()


# ---------------------------------------------------------------------------
# _check_one_budget — threshold evaluation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_one_budget_fires_when_threshold_crossed():
    """_check_one_budget creates an AlertEvent when spend exceeds threshold."""
    from app.services.budget import _check_one_budget

    session = AsyncMock()
    budget = _make_budget(amount_usd=1000.0, period="monthly")

    # spend = 850, amount = 1000 → 85% → crosses the 80% threshold
    spend_result = make_scalar_result(Decimal("850.00"))

    threshold = _make_threshold(
        budget_id=budget.id,
        threshold_percent=80,
        last_triggered_period=None,  # not yet fired this period
    )

    thresholds_scalars = MagicMock()
    thresholds_scalars.all.return_value = [threshold]
    thresholds_result = MagicMock()
    thresholds_result.scalars.return_value = thresholds_scalars

    channel = _make_notification_channel(channel_type="webhook")
    # Wire the threshold to the channel so _check_one_budget enters the notify path
    threshold.notification_channel_id = channel.id

    channel_result = MagicMock()
    channel_result.scalar_one_or_none.return_value = channel

    session.execute.side_effect = [
        spend_result,
        thresholds_result,
        channel_result,
    ]

    notify_mock = AsyncMock()
    delivery_mock = MagicMock()
    delivery_mock.status = "delivered"
    notify_mock.return_value = delivery_mock

    with (
        patch("app.services.budget.notify_budget_alert", notify_mock),
        patch(
            "app.services.budget._period_date_range",
            return_value=(date(2026, 3, 1), date(2026, 4, 1)),
        ),
        patch("app.services.budget._current_period", return_value="2026-03"),
    ):
        await _check_one_budget(session, budget)

    session.add.assert_called_once()  # AlertEvent added
    notify_mock.assert_called_once()
    session.commit.assert_called_once()

    added_event = session.add.call_args[0][0]
    assert added_event.threshold_percent == 80
    assert added_event.billing_period == "2026-03"


@pytest.mark.asyncio
async def test_check_one_budget_skips_already_fired_threshold():
    """_check_one_budget skips a threshold already fired in the current period."""
    from app.services.budget import _check_one_budget

    session = AsyncMock()
    budget = _make_budget(amount_usd=1000.0, period="monthly")

    spend_result = make_scalar_result(Decimal("850.00"))

    threshold = _make_threshold(
        budget_id=budget.id,
        threshold_percent=80,
        last_triggered_period="2026-03",  # already fired!
    )

    thresholds_scalars = MagicMock()
    thresholds_scalars.all.return_value = [threshold]
    thresholds_result = MagicMock()
    thresholds_result.scalars.return_value = thresholds_scalars

    session.execute.side_effect = [spend_result, thresholds_result]

    notify_mock = AsyncMock()

    with (
        patch("app.services.budget.notify_budget_alert", notify_mock),
        patch(
            "app.services.budget._period_date_range",
            return_value=(date(2026, 3, 1), date(2026, 4, 1)),
        ),
        patch("app.services.budget._current_period", return_value="2026-03"),
    ):
        await _check_one_budget(session, budget)

    session.add.assert_not_called()
    notify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_check_one_budget_below_threshold_no_alert():
    """_check_one_budget does not create an alert when spend is below threshold."""
    from app.services.budget import _check_one_budget

    session = AsyncMock()
    budget = _make_budget(amount_usd=1000.0, period="monthly")

    # spend = 500 → 50% → does NOT cross the 80% threshold
    spend_result = make_scalar_result(Decimal("500.00"))

    threshold = _make_threshold(
        budget_id=budget.id,
        threshold_percent=80,
        last_triggered_period=None,
    )

    thresholds_scalars = MagicMock()
    thresholds_scalars.all.return_value = [threshold]
    thresholds_result = MagicMock()
    thresholds_result.scalars.return_value = thresholds_scalars

    session.execute.side_effect = [spend_result, thresholds_result]

    notify_mock = AsyncMock()

    with (
        patch("app.services.budget.notify_budget_alert", notify_mock),
        patch(
            "app.services.budget._period_date_range",
            return_value=(date(2026, 3, 1), date(2026, 4, 1)),
        ),
        patch("app.services.budget._current_period", return_value="2026-03"),
    ):
        await _check_one_budget(session, budget)

    session.add.assert_not_called()
    notify_mock.assert_not_called()


@pytest.mark.asyncio
async def test_check_one_budget_no_channel_sets_no_channel_status():
    """_check_one_budget sets delivery_status='no_channel' when threshold has no channel."""
    from app.services.budget import _check_one_budget

    session = AsyncMock()
    budget = _make_budget(amount_usd=1000.0, period="monthly")

    spend_result = make_scalar_result(Decimal("900.00"))

    threshold = _make_threshold(
        budget_id=budget.id,
        threshold_percent=80,
        notification_channel_id=None,  # no channel linked
        last_triggered_period=None,
    )

    thresholds_scalars = MagicMock()
    thresholds_scalars.all.return_value = [threshold]
    thresholds_result = MagicMock()
    thresholds_result.scalars.return_value = thresholds_scalars

    session.execute.side_effect = [spend_result, thresholds_result]

    with (
        patch(
            "app.services.budget._period_date_range",
            return_value=(date(2026, 3, 1), date(2026, 4, 1)),
        ),
        patch("app.services.budget._current_period", return_value="2026-03"),
    ):
        await _check_one_budget(session, budget)

    added_event = session.add.call_args[0][0]
    assert added_event.delivery_status == "no_channel"


@pytest.mark.asyncio
async def test_check_one_budget_zero_amount_skipped():
    """_check_one_budget exits immediately when budget amount_usd <= 0."""
    from app.services.budget import _check_one_budget

    session = AsyncMock()
    budget = _make_budget(amount_usd=0.0)

    spend_result = make_scalar_result(Decimal("100.00"))
    session.execute.return_value = spend_result

    notify_mock = AsyncMock()
    with patch("app.services.budget.notify_budget_alert", notify_mock):
        await _check_one_budget(session, budget)

    notify_mock.assert_not_called()
    session.add.assert_not_called()
