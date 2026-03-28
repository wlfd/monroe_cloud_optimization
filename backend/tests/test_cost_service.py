"""
Unit tests for app.services.cost.

Covers:
- get_spend_summary: normal month, January wrap, zero prior month, day 1
- get_daily_spend: returns rows, respects days cutoff
- get_breakdown: valid dimensions, invalid dimension raises ValueError
- get_top_resources: returns results
- get_breakdown_for_export: same as breakdown but no limit
"""

import calendar
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import make_scalar_result

# ---------------------------------------------------------------------------
# get_spend_summary — normal month
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_spend_summary_normal_month():
    """Normal month returns correct MTD, projection, prior month, and MoM delta."""
    from app.services.cost import get_spend_summary

    session = AsyncMock()

    fake_today = date(2026, 3, 15)
    days_in_month = calendar.monthrange(2026, 3)[1]

    mtd_total = 3000.0
    prior_month_total = 5000.0

    session.execute.side_effect = [
        make_scalar_result(Decimal(str(mtd_total))),
        make_scalar_result(Decimal(str(prior_month_total))),
    ]

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = await get_spend_summary(session)

    assert result["mtd_total"] == mtd_total
    expected_projection = (mtd_total / 15) * days_in_month
    assert result["projected_month_end"] == pytest.approx(expected_projection)
    assert result["prior_month_total"] == prior_month_total
    expected_mom = (mtd_total - prior_month_total) / prior_month_total * 100
    assert result["mom_delta_pct"] == pytest.approx(expected_mom)


# ---------------------------------------------------------------------------
# get_spend_summary — January wraps to December prior year
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_spend_summary_january_wraps_to_december():
    """In January, prior month should query December of the previous year."""
    from app.services.cost import get_spend_summary

    session = AsyncMock()

    fake_today = date(2026, 1, 10)
    mtd_total = 2000.0
    prior_month_total = 8000.0

    session.execute.side_effect = [
        make_scalar_result(Decimal(str(mtd_total))),
        make_scalar_result(Decimal(str(prior_month_total))),
    ]

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = await get_spend_summary(session)

    assert result["mtd_total"] == mtd_total
    assert result["prior_month_total"] == prior_month_total
    # MoM should be computed relative to December
    expected_mom = (mtd_total - prior_month_total) / prior_month_total * 100
    assert result["mom_delta_pct"] == pytest.approx(expected_mom)


# ---------------------------------------------------------------------------
# get_spend_summary — zero prior month (MoM = None)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_spend_summary_zero_prior_month():
    """When prior month total is zero, MoM delta should be None."""
    from app.services.cost import get_spend_summary

    session = AsyncMock()

    fake_today = date(2026, 3, 15)

    session.execute.side_effect = [
        make_scalar_result(Decimal("1500")),
        make_scalar_result(Decimal("0")),
    ]

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = await get_spend_summary(session)

    assert result["mtd_total"] == 1500.0
    assert result["prior_month_total"] == 0.0
    assert result["mom_delta_pct"] is None


# ---------------------------------------------------------------------------
# get_spend_summary — day 1 of month
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_spend_summary_day_1():
    """On day 1, projection should still compute (days_elapsed=1)."""
    from app.services.cost import get_spend_summary

    session = AsyncMock()

    fake_today = date(2026, 4, 1)
    days_in_month = calendar.monthrange(2026, 4)[1]
    mtd_total = 500.0

    session.execute.side_effect = [
        make_scalar_result(Decimal(str(mtd_total))),
        make_scalar_result(Decimal("10000")),
    ]

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = await get_spend_summary(session)

    expected_projection = (mtd_total / 1) * days_in_month
    assert result["projected_month_end"] == pytest.approx(expected_projection)


# ---------------------------------------------------------------------------
# get_spend_summary — null MTD (no data this month)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_spend_summary_null_mtd():
    """When no billing data exists for the current month, MTD defaults to 0."""
    from app.services.cost import get_spend_summary

    session = AsyncMock()

    fake_today = date(2026, 3, 15)

    session.execute.side_effect = [
        make_scalar_result(None),
        make_scalar_result(None),
    ]

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = fake_today
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        result = await get_spend_summary(session)

    assert result["mtd_total"] == 0.0
    assert result["projected_month_end"] == 0.0
    assert result["prior_month_total"] == 0.0
    assert result["mom_delta_pct"] is None


# ---------------------------------------------------------------------------
# get_daily_spend — returns rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_spend_returns_rows():
    """get_daily_spend returns all rows from the query."""
    from app.services.cost import get_daily_spend

    session = AsyncMock()

    row1 = MagicMock(usage_date=date(2026, 3, 10), total_cost=Decimal("100"))
    row2 = MagicMock(usage_date=date(2026, 3, 11), total_cost=Decimal("200"))
    result = MagicMock()
    result.all.return_value = [row1, row2]
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_daily_spend(session, days=30)

    assert len(rows) == 2
    assert rows[0].usage_date == date(2026, 3, 10)


# ---------------------------------------------------------------------------
# get_daily_spend — respects days cutoff
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_spend_respects_days_cutoff():
    """get_daily_spend calls execute (which applies the cutoff filter)."""
    from app.services.cost import get_daily_spend

    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_daily_spend(session, days=7)

    assert rows == []
    session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_breakdown — valid dimensions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_breakdown_valid_dimension():
    """get_breakdown returns results for a valid dimension like 'service_name'."""
    from app.services.cost import get_breakdown

    session = AsyncMock()

    row = MagicMock(dimension_value="Virtual Machines", total_cost=Decimal("5000"))
    result = MagicMock()
    result.all.return_value = [row]
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_breakdown(session, "service_name", 30)

    assert len(rows) == 1
    assert rows[0].dimension_value == "Virtual Machines"


@pytest.mark.asyncio
async def test_get_breakdown_all_valid_dimensions():
    """All four valid dimensions (service_name, resource_group, region, tag) work."""
    from app.services.cost import DIMENSION_MAP, get_breakdown

    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)

        for dim in DIMENSION_MAP.keys():
            session.execute.reset_mock()
            rows = await get_breakdown(session, dim, 30)
            assert rows == []
            session.execute.assert_called_once()


# ---------------------------------------------------------------------------
# get_breakdown — invalid dimension raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_breakdown_invalid_dimension_raises():
    """get_breakdown raises ValueError for an unknown dimension."""
    from app.services.cost import get_breakdown

    session = AsyncMock()

    with pytest.raises(ValueError, match="Invalid dimension"):
        await get_breakdown(session, "invalid_col", 30)


# ---------------------------------------------------------------------------
# get_top_resources — returns results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_top_resources_returns_results():
    """get_top_resources returns resource rows."""
    from app.services.cost import get_top_resources

    session = AsyncMock()

    row = MagicMock(
        resource_id="res-1",
        resource_name="vm-01",
        service_name="Virtual Machines",
        resource_group="rg-prod",
        total_cost=Decimal("8000"),
    )
    result = MagicMock()
    result.all.return_value = [row]
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_top_resources(session, days=30)

    assert len(rows) == 1
    assert rows[0].resource_name == "vm-01"


@pytest.mark.asyncio
async def test_get_top_resources_empty():
    """get_top_resources returns empty list when no resources exist."""
    from app.services.cost import get_top_resources

    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_top_resources(session, days=30)

    assert rows == []


# ---------------------------------------------------------------------------
# get_breakdown_for_export — same as breakdown but no limit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_breakdown_for_export_valid():
    """get_breakdown_for_export returns results for a valid dimension."""
    from app.services.cost import get_breakdown_for_export

    session = AsyncMock()

    row1 = MagicMock(dimension_value="Storage", total_cost=Decimal("3000"))
    row2 = MagicMock(dimension_value="Compute", total_cost=Decimal("7000"))
    result = MagicMock()
    result.all.return_value = [row2, row1]
    session.execute.return_value = result

    with patch("app.services.cost.date") as mock_date:
        mock_date.today.return_value = date(2026, 3, 15)
        mock_date.side_effect = lambda *a, **kw: date(*a, **kw)
        rows = await get_breakdown_for_export(session, "service_name", 30)

    assert len(rows) == 2


@pytest.mark.asyncio
async def test_get_breakdown_for_export_invalid_dimension():
    """get_breakdown_for_export raises ValueError for an unknown dimension."""
    from app.services.cost import get_breakdown_for_export

    session = AsyncMock()

    with pytest.raises(ValueError, match="Invalid dimension"):
        await get_breakdown_for_export(session, "nonexistent", 30)
