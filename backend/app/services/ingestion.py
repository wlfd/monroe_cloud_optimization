"""Ingestion orchestration service.

Coordinates all ingestion operations: delta window calculation, idempotent upsert,
24-month backfill, run logging, alert management, and concurrency guard.

Uses AsyncSessionLocal directly (not get_db dependency) because scheduler jobs run
outside of request context (Pattern 7 from research).
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone, date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.billing import BillingRecord, IngestionRun, IngestionAlert
from app.services.anomaly import run_anomaly_detection
from app.services.attribution import run_attribution
from app.services.azure_client import fetch_with_retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Concurrency guard — module-level state
# ---------------------------------------------------------------------------

_ingestion_lock = asyncio.Lock()
_ingestion_running: bool = False


def is_ingestion_running() -> bool:
    """Return True if an ingestion run is currently active."""
    return _ingestion_running


# ---------------------------------------------------------------------------
# Run query helpers
# ---------------------------------------------------------------------------


async def get_last_successful_run(session: AsyncSession) -> IngestionRun | None:
    """Return the most recent successful IngestionRun, or None if none exist."""
    stmt = (
        select(IngestionRun)
        .where(IngestionRun.status == "success")
        .order_by(IngestionRun.started_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Delta window
# ---------------------------------------------------------------------------

MAX_CATCHUP_DAYS = 7


async def compute_delta_window(session: AsyncSession) -> tuple[datetime, datetime]:
    """Calculate the (start, end) window for the next incremental fetch.

    Decision: 24h overlap applied to start to catch late-arriving Azure records
    (matches Pattern 6 from research — resolves the open question in favour of
    a 24-hour re-check window).

    Window is capped at MAX_CATCHUP_DAYS=7 to avoid overwhelming the API after
    an extended outage.

    If no prior successful run exists, returns (now - 4h, now) as the first
    scheduled-run window (backfill is handled separately).
    """
    now = datetime.now(timezone.utc)
    last_run = await get_last_successful_run(session)

    if last_run is None or last_run.window_end is None:
        # First scheduled run — use a small 4-hour window; backfill covers history.
        return now - timedelta(hours=4), now

    # Apply 24h overlap to catch late-arriving records, then cap at 7 days.
    raw_start = last_run.window_end - timedelta(hours=24)
    cap_start = now - timedelta(days=MAX_CATCHUP_DAYS)
    start = max(raw_start, cap_start)
    return start, now


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


def _parse_usage_date(raw: int) -> date:
    """Convert Azure YYYYMMDD integer (e.g. 20260131) to Python date."""
    return date(year=raw // 10000, month=(raw % 10000) // 100, day=raw % 100)


def _map_record(raw: dict) -> dict:
    """Map an Azure API response row dict to BillingRecord column values."""
    usage_date_raw = raw.get("UsageDate")
    usage_date = _parse_usage_date(int(usage_date_raw)) if usage_date_raw is not None else None

    now = datetime.now(timezone.utc)

    # Derive resource_name from the last segment of ResourceId path
    resource_id = raw.get("ResourceId", "")
    resource_name = resource_id.split("/")[-1] if resource_id else ""

    return {
        "usage_date": usage_date,
        "subscription_id": raw.get("SubscriptionId", ""),
        "resource_group": raw.get("ResourceGroup", ""),
        "service_name": raw.get("ServiceName", ""),
        "meter_category": raw.get("MeterCategory", ""),
        "region": raw.get("ResourceLocation", ""),
        "tag": raw.get("tenant_id", ""),
        "resource_id": resource_id,
        "resource_name": resource_name,
        "pre_tax_cost": raw.get("PreTaxCost", 0.0),
        "currency": raw.get("Currency", "USD"),
        "ingested_at": now,
        "updated_at": now,
    }


async def upsert_billing_records(session: AsyncSession, records: list[dict]) -> int:
    """Idempotently insert or update billing records.

    Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE so that re-running against
    the same date range produces no duplicate rows.

    Conflict target: (usage_date, subscription_id, resource_group, service_name, meter_category)
    On conflict: update pre_tax_cost, currency, updated_at.

    Returns the number of rows affected.
    """
    if not records:
        return 0

    rows = [_map_record(r) for r in records]

    stmt = pg_insert(BillingRecord).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=["usage_date", "subscription_id", "resource_group", "service_name", "meter_category"],
        set_={
            "pre_tax_cost": stmt.excluded.pre_tax_cost,
            "currency": stmt.excluded.currency,
            "updated_at": stmt.excluded.updated_at,
        },
    )

    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


# ---------------------------------------------------------------------------
# Run logging
# ---------------------------------------------------------------------------


async def log_ingestion_run(
    session: AsyncSession,
    *,
    status: str,
    records_ingested: int = 0,
    error_detail: str | None = None,
    triggered_by: str,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
    retry_count: int = 0,
) -> IngestionRun:
    """Create and commit an IngestionRun row with the final status."""
    run = IngestionRun(
        status=status,
        triggered_by=triggered_by,
        records_ingested=records_ingested,
        error_detail=error_detail,
        window_start=window_start,
        window_end=window_end,
        retry_count=retry_count,
        completed_at=datetime.now(timezone.utc),
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


# ---------------------------------------------------------------------------
# Alert management
# ---------------------------------------------------------------------------


async def create_ingestion_alert(
    session: AsyncSession,
    *,
    error_detail: str,
    retry_count: int = 3,
) -> IngestionAlert:
    """Create an active IngestionAlert row recording the failure."""
    now = datetime.now(timezone.utc)
    alert = IngestionAlert(
        error_message=error_detail,
        retry_count=retry_count,
        failed_at=now,
        is_active=True,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def clear_active_alerts(session: AsyncSession) -> None:
    """Clear all active IngestionAlert rows after a successful ingestion.

    Sets is_active=False, cleared_at=utcnow(), cleared_by='auto_success'.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        update(IngestionAlert)
        .where(IngestionAlert.is_active == True)  # noqa: E712
        .values(is_active=False, cleared_at=now, cleared_by="auto_success")
    )
    await session.execute(stmt)
    await session.commit()


# ---------------------------------------------------------------------------
# Stale run recovery
# ---------------------------------------------------------------------------


async def recover_stale_runs(session: AsyncSession) -> None:
    """Mark any 'running' IngestionRun rows as 'interrupted'.

    Called at app startup to prevent stale 'running' status after a crash restart
    (Pitfall 5 from research).
    """
    stmt = (
        update(IngestionRun)
        .where(IngestionRun.status == "running")
        .values(status="interrupted", completed_at=datetime.now(timezone.utc))
    )
    result = await session.execute(stmt)
    await session.commit()
    if result.rowcount:
        logger.warning("recover_stale_runs: marked %d run(s) as interrupted", result.rowcount)


# ---------------------------------------------------------------------------
# Backfill
# ---------------------------------------------------------------------------


async def run_backfill(session: AsyncSession) -> None:
    """Perform a chunked 24-month historical backfill.

    Skips if any successful run already exists (prevents re-triggering on restart).
    Processes 24 monthly (30-day) chunks with asyncio.sleep(1) throttle between
    calls to respect Azure QPU quota (12 QPU / 10s).
    """
    settings = get_settings()
    existing = await get_last_successful_run(session)
    if existing is not None:
        logger.info("run_backfill: prior successful run found — skipping backfill")
        return

    scope = settings.AZURE_SUBSCRIPTION_SCOPE or f"/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}"
    now = datetime.now(timezone.utc)
    chunk_days = 30

    logger.info("run_backfill: starting 24-month historical backfill")

    for i in range(24):
        chunk_end = now - timedelta(days=i * chunk_days)
        chunk_start = chunk_end - timedelta(days=chunk_days)

        try:
            records = await fetch_with_retry(scope=scope, start=chunk_start, end=chunk_end)
            await upsert_billing_records(session, records)
            logger.info(
                "run_backfill: chunk %d/24 done (start=%s, end=%s, records=%d)",
                i + 1,
                chunk_start.date(),
                chunk_end.date(),
                len(records),
            )
        except Exception as exc:
            logger.error("run_backfill: chunk %d failed: %s", i + 1, exc)
            raise

        if i < 23:
            await asyncio.sleep(1)  # QPU throttle: 12 QPU / 10s budget

    await log_ingestion_run(
        session,
        status="success",
        triggered_by="backfill",
        records_ingested=0,  # Individual upsert calls track rowcounts separately
    )
    logger.info("run_backfill: 24-month backfill complete")


# ---------------------------------------------------------------------------
# Core orchestration
# ---------------------------------------------------------------------------


async def _do_ingestion(triggered_by: str) -> None:
    """Core ingestion logic — runs inside the concurrency lock.

    On first run (no prior successful run): delegates to run_backfill.
    On subsequent runs: fetches the delta window and upserts results.
    """
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        run_start = datetime.now(timezone.utc)
        try:
            last_run = await get_last_successful_run(session)
            if last_run is None and triggered_by != "backfill":
                await run_backfill(session)
                return

            start, end = await compute_delta_window(session)
            scope = (
                settings.AZURE_SUBSCRIPTION_SCOPE
                or f"/subscriptions/{settings.AZURE_SUBSCRIPTION_ID}"
            )
            records = await fetch_with_retry(scope=scope, start=start, end=end)
            count = await upsert_billing_records(session, records)
            await run_anomaly_detection(session)
            try:
                await run_attribution()
                logger.info("Attribution run completed after ingestion")
            except Exception as exc:
                logger.error("Attribution run failed after ingestion: %s", exc)
                # Non-fatal — attribution failure does not fail the ingestion run record
            await clear_active_alerts(session)
            await log_ingestion_run(
                session,
                status="success",
                records_ingested=count,
                triggered_by=triggered_by,
                window_start=start,
                window_end=end,
            )
            logger.info(
                "_do_ingestion: success (triggered_by=%s, records=%d, window=%s→%s)",
                triggered_by,
                count,
                start.isoformat(),
                end.isoformat(),
            )
        except Exception as exc:
            logger.error("_do_ingestion: failed (triggered_by=%s): %s", triggered_by, exc)
            async with AsyncSessionLocal() as err_session:
                await log_ingestion_run(
                    err_session,
                    status="failed",
                    error_detail=str(exc),
                    triggered_by=triggered_by,
                )
                await create_ingestion_alert(err_session, error_detail=str(exc), retry_count=3)
            raise


async def run_ingestion(triggered_by: str = "scheduler") -> None:
    """Public entry point for triggering an ingestion run.

    Concurrency guard: if the lock is already acquired, returns immediately
    without starting a second run (idempotent under concurrent callers).
    """
    global _ingestion_running
    if _ingestion_lock.locked():
        logger.info("run_ingestion: already running — skipping (triggered_by=%s)", triggered_by)
        return
    async with _ingestion_lock:
        _ingestion_running = True
        try:
            await _do_ingestion(triggered_by)
        finally:
            _ingestion_running = False
