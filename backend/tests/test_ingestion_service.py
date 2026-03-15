"""
Unit tests for app.services.ingestion.

Covers:
- _parse_usage_date and _map_record field mapping
- compute_delta_window: first run, normal run, cap-at-7-days
- upsert_billing_records: empty input, mapping, rowcount
- log_ingestion_run: creates IngestionRun row
- create_ingestion_alert / clear_active_alerts
- recover_stale_runs: marks 'running' rows as 'interrupted'
- is_ingestion_running: concurrency flag
- run_ingestion: concurrent guard (skips second call)
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from tests.conftest import make_scalar_result, make_scalars_result


# ---------------------------------------------------------------------------
# _parse_usage_date
# ---------------------------------------------------------------------------


def test_parse_usage_date_standard():
    """_parse_usage_date converts YYYYMMDD integer to a Python date."""
    from app.services.ingestion import _parse_usage_date

    result = _parse_usage_date(20260131)
    assert result == date(2026, 1, 31)


def test_parse_usage_date_jan_first():
    """_parse_usage_date handles Jan 1st correctly."""
    from app.services.ingestion import _parse_usage_date

    result = _parse_usage_date(20260101)
    assert result == date(2026, 1, 1)


def test_parse_usage_date_dec_31():
    """_parse_usage_date handles Dec 31st correctly."""
    from app.services.ingestion import _parse_usage_date

    result = _parse_usage_date(20261231)
    assert result == date(2026, 12, 31)


# ---------------------------------------------------------------------------
# _map_record
# ---------------------------------------------------------------------------


def test_map_record_basic_fields():
    """_map_record extracts all expected fields from an Azure row dict."""
    from app.services.ingestion import _map_record

    raw = {
        "UsageDate": 20260301,
        "SubscriptionId": "sub-abc",
        "ResourceGroup": "rg-prod",
        "ServiceName": "Virtual Machines",
        "MeterCategory": "Compute",
        "ResourceLocation": "eastus",
        "tenant_id": "tenant-a",
        "ResourceId": "/subscriptions/sub-abc/resourceGroups/rg-prod/providers/Microsoft.Compute/virtualMachines/my-vm",
        "PreTaxCost": 45.67,
        "Currency": "USD",
    }

    result = _map_record(raw)

    assert result["usage_date"] == date(2026, 3, 1)
    assert result["subscription_id"] == "sub-abc"
    assert result["resource_group"] == "rg-prod"
    assert result["service_name"] == "Virtual Machines"
    assert result["meter_category"] == "Compute"
    assert result["region"] == "eastus"
    assert result["tag"] == "tenant-a"
    assert result["resource_name"] == "my-vm"
    assert result["pre_tax_cost"] == 45.67
    assert result["currency"] == "USD"
    assert "ingested_at" in result
    assert "updated_at" in result


def test_map_record_missing_resource_id_gives_empty_name():
    """_map_record handles missing ResourceId gracefully."""
    from app.services.ingestion import _map_record

    raw = {
        "UsageDate": 20260301,
        "SubscriptionId": "sub-abc",
        "ResourceGroup": "rg-prod",
        "ServiceName": "Networking",
        "MeterCategory": "Networking",
        "PreTaxCost": 0.0,
        "Currency": "USD",
    }

    result = _map_record(raw)
    assert result["resource_name"] == ""
    assert result["resource_id"] == ""


def test_map_record_missing_usage_date():
    """_map_record handles missing UsageDate by setting usage_date=None."""
    from app.services.ingestion import _map_record

    raw = {
        "SubscriptionId": "sub-abc",
        "ResourceGroup": "rg-prod",
        "ServiceName": "Storage",
        "MeterCategory": "Storage",
        "PreTaxCost": 10.0,
        "Currency": "USD",
    }

    result = _map_record(raw)
    assert result["usage_date"] is None


# ---------------------------------------------------------------------------
# compute_delta_window
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compute_delta_window_no_prior_run():
    """First run with no prior success returns a 4-hour window ending now."""
    from app.services.ingestion import compute_delta_window

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    start, end = await compute_delta_window(session)

    now = datetime.now(timezone.utc)
    # start should be ~4 hours before now
    assert abs((end - now).total_seconds()) < 5
    assert abs((end - start).total_seconds() - 4 * 3600) < 5


@pytest.mark.asyncio
async def test_compute_delta_window_normal_run():
    """Normal run applies 24h overlap: start = last_window_end - 24h."""
    from app.services.ingestion import compute_delta_window

    session = AsyncMock()
    last_run = MagicMock()
    last_window_end = datetime.now(timezone.utc) - timedelta(hours=2)
    last_run.window_end = last_window_end
    result = MagicMock()
    result.scalar_one_or_none.return_value = last_run
    session.execute.return_value = result

    start, end = await compute_delta_window(session)

    expected_start = last_window_end - timedelta(hours=24)
    assert abs((start - expected_start).total_seconds()) < 5


@pytest.mark.asyncio
async def test_compute_delta_window_capped_at_7_days():
    """If the last run ended 14 days ago, start is capped at 7 days ago."""
    from app.services.ingestion import compute_delta_window

    session = AsyncMock()
    last_run = MagicMock()
    last_run.window_end = datetime.now(timezone.utc) - timedelta(days=14)
    result = MagicMock()
    result.scalar_one_or_none.return_value = last_run
    session.execute.return_value = result

    start, end = await compute_delta_window(session)

    cap_start = datetime.now(timezone.utc) - timedelta(days=7)
    # start should be approximately 7 days ago (not 14 + 1 days)
    assert abs((start - cap_start).total_seconds()) < 10


@pytest.mark.asyncio
async def test_compute_delta_window_none_window_end_treated_as_first_run():
    """A IngestionRun with window_end=None is treated like no prior run."""
    from app.services.ingestion import compute_delta_window

    session = AsyncMock()
    last_run = MagicMock()
    last_run.window_end = None
    result = MagicMock()
    result.scalar_one_or_none.return_value = last_run
    session.execute.return_value = result

    start, end = await compute_delta_window(session)

    now = datetime.now(timezone.utc)
    assert abs((end - start).total_seconds() - 4 * 3600) < 5


# ---------------------------------------------------------------------------
# upsert_billing_records
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_billing_records_empty_input_returns_zero():
    """upsert_billing_records returns 0 and skips DB on empty input."""
    from app.services.ingestion import upsert_billing_records

    session = AsyncMock()
    count = await upsert_billing_records(session, [])

    assert count == 0
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_upsert_billing_records_returns_rowcount():
    """upsert_billing_records returns the rowcount from the DB execute result."""
    from app.services.ingestion import upsert_billing_records

    session = AsyncMock()
    db_result = MagicMock()
    db_result.rowcount = 3
    session.execute.return_value = db_result

    raw_records = [
        {
            "UsageDate": 20260301,
            "SubscriptionId": "sub-001",
            "ResourceGroup": "rg-prod",
            "ServiceName": "Compute",
            "MeterCategory": "Compute",
            "PreTaxCost": 10.0,
            "Currency": "USD",
        },
        {
            "UsageDate": 20260301,
            "SubscriptionId": "sub-001",
            "ResourceGroup": "rg-data",
            "ServiceName": "Storage",
            "MeterCategory": "Storage",
            "PreTaxCost": 5.0,
            "Currency": "USD",
        },
        {
            "UsageDate": 20260302,
            "SubscriptionId": "sub-001",
            "ResourceGroup": "rg-prod",
            "ServiceName": "Networking",
            "MeterCategory": "Networking",
            "PreTaxCost": 2.0,
            "Currency": "USD",
        },
    ]

    count = await upsert_billing_records(session, raw_records)

    assert count == 3
    session.execute.assert_called_once()
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# log_ingestion_run
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_log_ingestion_run_creates_row():
    """log_ingestion_run creates and commits an IngestionRun with given fields."""
    from app.services.ingestion import log_ingestion_run

    session = AsyncMock()
    now = datetime.now(timezone.utc)
    run = await log_ingestion_run(
        session,
        status="success",
        records_ingested=42,
        triggered_by="manual",
        window_start=now - timedelta(hours=4),
        window_end=now,
    )

    session.add.assert_called_once()
    session.commit.assert_called_once()
    session.refresh.assert_called_once()

    # The run returned is the object passed to session.add
    added_obj = session.add.call_args[0][0]
    assert added_obj.status == "success"
    assert added_obj.records_ingested == 42
    assert added_obj.triggered_by == "manual"


# ---------------------------------------------------------------------------
# create_ingestion_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_ingestion_alert_sets_is_active():
    """create_ingestion_alert creates an active alert row."""
    from app.services.ingestion import create_ingestion_alert

    session = AsyncMock()
    alert = await create_ingestion_alert(
        session,
        error_detail="Azure API timeout",
        retry_count=3,
    )

    session.add.assert_called_once()
    session.commit.assert_called_once()

    added_obj = session.add.call_args[0][0]
    assert added_obj.is_active is True
    assert added_obj.error_message == "Azure API timeout"
    assert added_obj.retry_count == 3


# ---------------------------------------------------------------------------
# clear_active_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_active_alerts_updates_all_active():
    """clear_active_alerts issues an UPDATE to mark all active alerts inactive."""
    from app.services.ingestion import clear_active_alerts

    session = AsyncMock()
    db_result = MagicMock()
    db_result.rowcount = 2
    session.execute.return_value = db_result

    await clear_active_alerts(session)

    session.execute.assert_called_once()
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# recover_stale_runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recover_stale_runs_marks_interrupted():
    """recover_stale_runs updates 'running' rows to 'interrupted'."""
    from app.services.ingestion import recover_stale_runs

    session = AsyncMock()
    db_result = MagicMock()
    db_result.rowcount = 1
    session.execute.return_value = db_result

    with patch("app.services.ingestion.logger") as mock_logger:
        await recover_stale_runs(session)

    session.execute.assert_called_once()
    session.commit.assert_called_once()
    mock_logger.warning.assert_called_once()


@pytest.mark.asyncio
async def test_recover_stale_runs_no_stale_no_warning():
    """recover_stale_runs logs nothing when no stale runs exist."""
    from app.services.ingestion import recover_stale_runs

    session = AsyncMock()
    db_result = MagicMock()
    db_result.rowcount = 0
    session.execute.return_value = db_result

    with patch("app.services.ingestion.logger") as mock_logger:
        await recover_stale_runs(session)

    mock_logger.warning.assert_not_called()


# ---------------------------------------------------------------------------
# is_ingestion_running
# ---------------------------------------------------------------------------


def test_is_ingestion_running_default_false():
    """is_ingestion_running returns False before any run has started."""
    from app.services.ingestion import is_ingestion_running
    import app.services.ingestion as svc

    svc._ingestion_running = False
    assert is_ingestion_running() is False


# ---------------------------------------------------------------------------
# run_ingestion — concurrent guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_ingestion_skips_when_already_running():
    """run_ingestion returns immediately if the lock is already held."""
    import app.services.ingestion as svc

    # Simulate lock already acquired
    await svc._ingestion_lock.acquire()
    try:
        with patch("app.services.ingestion._do_ingestion", new_callable=AsyncMock) as mock_do:
            await svc.run_ingestion(triggered_by="scheduler")
            mock_do.assert_not_called()
    finally:
        svc._ingestion_lock.release()


@pytest.mark.asyncio
async def test_run_ingestion_sets_and_clears_running_flag():
    """run_ingestion sets _ingestion_running=True while running, False after."""
    import app.services.ingestion as svc

    flags_during = []

    async def fake_do(triggered_by: str):
        flags_during.append(svc._ingestion_running)

    with patch("app.services.ingestion._do_ingestion", side_effect=fake_do):
        await svc.run_ingestion(triggered_by="manual")

    assert flags_during == [True]
    assert svc._ingestion_running is False


@pytest.mark.asyncio
async def test_run_ingestion_clears_flag_on_exception():
    """run_ingestion resets _ingestion_running to False even if _do_ingestion raises."""
    import app.services.ingestion as svc

    async def raise_error(triggered_by: str):
        raise RuntimeError("Simulated failure")

    with patch("app.services.ingestion._do_ingestion", side_effect=raise_error):
        with pytest.raises(RuntimeError):
            await svc.run_ingestion(triggered_by="manual")

    assert svc._ingestion_running is False
