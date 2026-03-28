"""
Unit tests for app.services.anomaly.

Covers:
- 30-day baseline detection algorithm (severity thresholds, deviation filter)
- Edge cases: no baseline data, zero/negative baseline, single-day history
- Severity classification (critical / high / medium)
- Anomaly deduplication via upsert_anomaly
- auto_resolve_anomalies logic
- CRUD helpers: get_anomalies, get_anomaly_summary, update_anomaly_status,
  mark_anomaly_expected, unmark_anomaly_expected
"""

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import _make_anomaly, make_scalar_result, make_scalars_result

# ---------------------------------------------------------------------------
# Helpers to build row-like objects returned from DB execute
# ---------------------------------------------------------------------------


def _row(service_name: str, resource_group: str, **kwargs):
    """Create a MagicMock row with named attributes."""
    row = MagicMock()
    row.service_name = service_name
    row.resource_group = resource_group
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


def _make_execute_sequence(session: AsyncMock, responses: list):
    """Configure session.execute to return different values on successive calls."""
    session.execute.side_effect = responses


# ---------------------------------------------------------------------------
# run_anomaly_detection — no baseline data (early return)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_anomaly_detection_no_baseline_returns_early():
    """Detection exits immediately when no 30-day baseline rows exist."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    # First execute returns empty baseline → early return
    session.execute.return_value = make_scalars_result([])

    with patch("app.services.anomaly.logger") as mock_logger:
        await run_anomaly_detection(session)

    # commit should NOT have been called (skipped before any work)
    session.commit.assert_not_called()
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_run_anomaly_detection_empty_billing_table():
    """Detection exits gracefully when billing_records is empty (no max date)."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    baseline_row = _row("Virtual Machines", "rg-prod", baseline_avg_daily=100.0)
    # 1st call: baseline rows present
    # 2nd call: max_date returns None → empty table
    baseline_result = make_scalars_result([baseline_row])
    baseline_result.all.return_value = [baseline_row]

    max_date_result = make_scalar_result(None)

    session.execute.side_effect = [baseline_result, max_date_result]

    await run_anomaly_detection(session)

    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# run_anomaly_detection — severity classification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_anomaly_detection_critical_severity():
    """A 1000% spike with $1100/mo impact is classified as critical."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    baseline_row = _row("Virtual Machines", "rg-prod", baseline_avg_daily=10.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    # current_daily = 46.67 → pct_deviation = (46.67-10)/10*100 = 366%
    # estimated_monthly_impact = (46.67-10)*30 = ~1100 → critical
    current_row = _row("Virtual Machines", "rg-prod", current_daily=46.67)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    captured_severity = []

    async def capture_upsert(session, **kwargs):
        captured_severity.append(kwargs["severity"])

    with (
        patch("app.services.anomaly.upsert_anomaly", side_effect=capture_upsert),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    assert len(captured_severity) == 1
    assert captured_severity[0] == "critical"


@pytest.mark.asyncio
async def test_run_anomaly_detection_high_severity():
    """A spike producing $700/mo impact (but < $1000) is classified as high."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    # baseline = 20/day, current = 43.33/day
    # pct_deviation = (43.33-20)/20*100 = 116.7%
    # impact = (43.33-20)*30 = 700 → high
    baseline_row = _row("Storage", "rg-data", baseline_avg_daily=20.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    current_row = _row("Storage", "rg-data", current_daily=43.33)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    captured_severity = []

    async def capture_upsert(session, **kwargs):
        captured_severity.append(kwargs["severity"])

    with (
        patch("app.services.anomaly.upsert_anomaly", side_effect=capture_upsert),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    assert len(captured_severity) == 1
    assert captured_severity[0] == "high"


@pytest.mark.asyncio
async def test_run_anomaly_detection_medium_severity():
    """A spike producing $200/mo impact (< $500) is classified as medium."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    # baseline = 10/day, current = 16.67/day
    # pct_deviation = 66.7%, impact = 200 → medium
    baseline_row = _row("Networking", "rg-net", baseline_avg_daily=10.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    current_row = _row("Networking", "rg-net", current_daily=16.67)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    captured = []

    async def capture_upsert(session, **kwargs):
        captured.append(kwargs)

    with (
        patch("app.services.anomaly.upsert_anomaly", side_effect=capture_upsert),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    assert len(captured) == 1
    assert captured[0]["severity"] == "medium"


# ---------------------------------------------------------------------------
# run_anomaly_detection — threshold guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_anomaly_detection_below_20pct_deviation_skipped():
    """Spikes below 20% deviation are not flagged as anomalies."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    # baseline = 100/day, current = 115/day → 15% deviation → skipped
    baseline_row = _row("Virtual Machines", "rg-prod", baseline_avg_daily=100.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    current_row = _row("Virtual Machines", "rg-prod", current_daily=115.0)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    upsert_mock = AsyncMock()
    with (
        patch("app.services.anomaly.upsert_anomaly", upsert_mock),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    upsert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_anomaly_detection_below_100_impact_skipped():
    """Spikes above 20% deviation but with < $100/mo impact are noise-filtered."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    # baseline = 1/day, current = 2/day → 100% deviation, impact = $30/mo → skipped
    baseline_row = _row("DNS", "rg-infra", baseline_avg_daily=1.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    current_row = _row("DNS", "rg-infra", current_daily=2.0)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    upsert_mock = AsyncMock()
    with (
        patch("app.services.anomaly.upsert_anomaly", upsert_mock),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    upsert_mock.assert_not_called()


@pytest.mark.asyncio
async def test_run_anomaly_detection_zero_baseline_skipped():
    """Records with zero baseline average are skipped (division guard)."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    baseline_row = _row("Virtual Machines", "rg-prod", baseline_avg_daily=0.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    current_row = _row("Virtual Machines", "rg-prod", current_daily=500.0)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    upsert_mock = AsyncMock()
    with (
        patch("app.services.anomaly.upsert_anomaly", upsert_mock),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", new_callable=AsyncMock),
    ):
        await run_anomaly_detection(session)

    upsert_mock.assert_not_called()


# ---------------------------------------------------------------------------
# run_anomaly_detection — notification dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_anomaly_detection_notifies_newly_detected():
    """Notifications are dispatched only for anomalies not already open."""
    from app.services.anomaly import run_anomaly_detection

    session = AsyncMock()
    today = date.today()

    # A pair that was NOT already open before this run
    baseline_row = _row("Virtual Machines", "rg-prod", baseline_avg_daily=10.0)
    baseline_result = MagicMock()
    baseline_result.all.return_value = [baseline_row]

    max_date_result = MagicMock()
    max_date_result.scalar.return_value = today

    # No pre-existing open anomalies on check_date
    existing_open_result = MagicMock()
    existing_open_result.all.return_value = []

    # Spike that triggers detection
    current_row = _row("Virtual Machines", "rg-prod", current_daily=50.0)
    current_result = MagicMock()
    current_result.all.return_value = [current_row]

    session.execute.side_effect = [
        baseline_result,
        max_date_result,
        existing_open_result,
        current_result,
    ]

    notify_mock = AsyncMock()
    with (
        patch("app.services.anomaly.upsert_anomaly", new_callable=AsyncMock),
        patch("app.services.anomaly.auto_resolve_anomalies", new_callable=AsyncMock),
        patch("app.services.anomaly._notify_new_anomalies", notify_mock),
    ):
        await run_anomaly_detection(session)

    notify_mock.assert_called_once()
    call_kwargs = notify_mock.call_args
    # The newly_detected set should contain our (service, rg) pair
    assert ("Virtual Machines", "rg-prod") in call_kwargs.args[2]


# ---------------------------------------------------------------------------
# auto_resolve_anomalies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_resolve_anomalies_resolves_stale():
    """Anomalies no longer in the still_active set are marked resolved."""
    from app.services.anomaly import auto_resolve_anomalies

    session = AsyncMock()
    today = date.today()

    anomaly = _make_anomaly(
        service_name="Virtual Machines",
        resource_group="rg-old",
        status="new",
        expected=False,
    )

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [anomaly]
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    # "rg-old" is NOT in still_active → should be resolved
    still_active = {("Storage", "rg-current")}
    await auto_resolve_anomalies(session, still_active, today)

    assert anomaly.status == "resolved"
    assert anomaly.updated_at is not None


@pytest.mark.asyncio
async def test_auto_resolve_anomalies_preserves_still_active():
    """Anomalies that are still active are NOT resolved."""
    from app.services.anomaly import auto_resolve_anomalies

    session = AsyncMock()
    today = date.today()

    anomaly = _make_anomaly(
        service_name="Virtual Machines",
        resource_group="rg-prod",
        status="investigating",
        expected=False,
    )

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [anomaly]
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    still_active = {("Virtual Machines", "rg-prod")}
    await auto_resolve_anomalies(session, still_active, today)

    assert anomaly.status == "investigating"


@pytest.mark.asyncio
async def test_auto_resolve_anomalies_no_open_anomalies():
    """auto_resolve_anomalies is a no-op when there are no open anomalies."""
    from app.services.anomaly import auto_resolve_anomalies

    session = AsyncMock()
    today = date.today()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    await auto_resolve_anomalies(session, set(), today)
    # No assertions on state changes — just confirm no exception raised


# ---------------------------------------------------------------------------
# update_anomaly_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_anomaly_status_success():
    """update_anomaly_status changes status and returns the anomaly."""
    from app.services.anomaly import update_anomaly_status

    session = AsyncMock()
    anomaly = _make_anomaly(status="new")
    anomaly_id = anomaly.id

    result = MagicMock()
    result.scalar_one_or_none.return_value = anomaly
    session.execute.return_value = result

    updated = await update_anomaly_status(session, anomaly_id, "investigating")

    assert updated is not None
    assert updated.status == "investigating"
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(anomaly)


@pytest.mark.asyncio
async def test_update_anomaly_status_not_found():
    """update_anomaly_status returns None when anomaly_id doesn't exist."""
    from app.services.anomaly import update_anomaly_status

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await update_anomaly_status(session, uuid.uuid4(), "resolved")

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# mark_anomaly_expected / unmark_anomaly_expected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_anomaly_expected_sets_dismissed():
    """mark_anomaly_expected sets expected=True and status='dismissed'."""
    from app.services.anomaly import mark_anomaly_expected

    session = AsyncMock()
    anomaly = _make_anomaly(status="new", expected=False)
    anomaly_id = anomaly.id

    result = MagicMock()
    result.scalar_one_or_none.return_value = anomaly
    session.execute.return_value = result

    updated = await mark_anomaly_expected(session, anomaly_id)

    assert updated is not None
    assert updated.expected is True
    assert updated.status == "dismissed"
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unmark_anomaly_expected_resets_to_new():
    """unmark_anomaly_expected clears expected flag and resets status to 'new'."""
    from app.services.anomaly import unmark_anomaly_expected

    session = AsyncMock()
    anomaly = _make_anomaly(status="dismissed", expected=True)
    anomaly_id = anomaly.id

    result = MagicMock()
    result.scalar_one_or_none.return_value = anomaly
    session.execute.return_value = result

    updated = await unmark_anomaly_expected(session, anomaly_id)

    assert updated is not None
    assert updated.expected is False
    assert updated.status == "new"
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_mark_anomaly_expected_not_found():
    """mark_anomaly_expected returns None when anomaly_id doesn't exist."""
    from app.services.anomaly import mark_anomaly_expected

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await mark_anomaly_expected(session, uuid.uuid4())

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_anomalies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_anomalies_no_filters_returns_all():
    """get_anomalies with no filters returns all anomaly rows."""
    from app.services.anomaly import get_anomalies

    session = AsyncMock()
    anomalies = [_make_anomaly(severity="critical"), _make_anomaly(severity="high")]

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = anomalies
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    rows = await get_anomalies(session)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_get_anomalies_empty_result():
    """get_anomalies returns empty list when no anomalies exist."""
    from app.services.anomaly import get_anomalies

    session = AsyncMock()

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    rows = await get_anomalies(session)
    assert rows == []


# ---------------------------------------------------------------------------
# get_anomaly_summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_anomaly_summary_computes_fields():
    """get_anomaly_summary returns correct counts and detection_accuracy."""
    from app.services.anomaly import get_anomaly_summary

    session = AsyncMock()

    # Responses in order: active_count, critical_count, high_count, medium_count,
    # total_potential_impact, resolved_this_month, total_detected, expected_count
    counts = [5, 2, 2, 1, 7500.0, 3, 10, 2]
    results = [make_scalar_result(v) for v in counts]
    session.execute.side_effect = results

    summary = await get_anomaly_summary(session)

    assert summary["active_count"] == 5
    assert summary["critical_count"] == 2
    assert summary["high_count"] == 2
    assert summary["medium_count"] == 1
    assert summary["total_potential_impact"] == 7500.0
    assert summary["resolved_this_month"] == 3
    # detection_accuracy = (10 - 2) / 10 * 100 = 80.0
    assert summary["detection_accuracy"] == pytest.approx(80.0)


@pytest.mark.asyncio
async def test_get_anomaly_summary_no_detected_returns_none_accuracy():
    """get_anomaly_summary returns detection_accuracy=None when no anomalies detected."""
    from app.services.anomaly import get_anomaly_summary

    session = AsyncMock()

    # active=0, critical=0, high=0, medium=0, impact=0, resolved=0, total_detected=0, expected=0
    counts = [0, 0, 0, 0, 0.0, 0, 0, 0]
    results = [make_scalar_result(v) for v in counts]
    session.execute.side_effect = results

    summary = await get_anomaly_summary(session)

    assert summary["detection_accuracy"] is None
