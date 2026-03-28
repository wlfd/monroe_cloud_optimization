"""Anomaly detection service.

Implements the 30-day rolling baseline detection algorithm, idempotent upsert,
auto-resolve, and CRUD helpers for anomaly lifecycle management.

Detection runs as a post-ingestion hook called from ingestion.py after a
successful upsert. All functions accept an AsyncSession parameter (same session
pattern as cost.py and ingestion.py).
"""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Anomaly, BillingRecord
from app.services.notification import notify_anomaly_detected

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Detection algorithm
# ---------------------------------------------------------------------------


async def run_anomaly_detection(session: AsyncSession) -> None:
    """Run the 30-day rolling baseline anomaly detection algorithm.

    Called from _do_ingestion() after a successful upsert of billing records.
    Writes detected anomalies to the anomalies table (upsert — re-detection
    updates metrics but preserves user-set status/expected).

    Algorithm:
    1. Compute 30-day baseline average daily cost per (service_name, resource_group).
    2. Guard: if no baseline data, log warning and return early.
    3. Find the most recent completed billing day (MAX usage_date in billing_records).
    4. Fetch current day's spend per (service_name, resource_group).
    5. Flag pairs where pct_deviation >= 20% AND estimated_monthly_impact >= 100.
    6. Classify severity: critical (>= $1000/mo), high (>= $500), medium (>= $100).
    7. Upsert detected anomalies; auto-resolve previously open ones that are no
       longer triggered.
    8. Commit once at the end.
    """
    # Step 1: Compute 30-day baseline average daily cost per (service, resource_group)
    baseline_cutoff = date.today() - timedelta(days=30)

    # Subquery: daily cost per (service_name, resource_group, usage_date) over baseline window
    daily_sub = (
        select(
            BillingRecord.service_name,
            BillingRecord.resource_group,
            BillingRecord.usage_date,
            func.sum(BillingRecord.pre_tax_cost).label("daily_cost"),
        )
        .where(BillingRecord.usage_date >= baseline_cutoff)
        .group_by(
            BillingRecord.service_name,
            BillingRecord.resource_group,
            BillingRecord.usage_date,
        )
        .subquery()
    )

    # Aggregate: average daily cost per (service, resource_group) = baseline
    baseline_stmt = select(
        daily_sub.c.service_name,
        daily_sub.c.resource_group,
        func.avg(daily_sub.c.daily_cost).label("baseline_avg_daily"),
    ).group_by(daily_sub.c.service_name, daily_sub.c.resource_group)

    baseline_rows = (await session.execute(baseline_stmt)).all()

    # Step 2: Guard — if no 30-day baseline data, skip detection
    if not baseline_rows:
        logger.warning("run_anomaly_detection: no 30-day baseline data found — skipping detection")
        return

    # Step 3: Find the most recent completed billing day
    max_date_stmt = select(func.max(BillingRecord.usage_date))
    check_date: date | None = (await session.execute(max_date_stmt)).scalar()

    if check_date is None:
        logger.warning("run_anomaly_detection: billing_records table is empty — skipping detection")
        return

    logger.info("run_anomaly_detection: check_date=%s", check_date)

    # Snapshot which (service, resource_group) pairs already have an open anomaly
    # on check_date before this run. Used after detection to find newly-created ones.
    existing_open_stmt = select(Anomaly.service_name, Anomaly.resource_group).where(
        Anomaly.detected_date == check_date,
        Anomaly.status.in_(["new", "investigating"]),
    )
    existing_open: set[tuple[str, str]] = {
        (r.service_name, r.resource_group)
        for r in (await session.execute(existing_open_stmt)).all()
    }

    # Step 4: Fetch current day's spend per (service_name, resource_group)
    current_stmt = (
        select(
            BillingRecord.service_name,
            BillingRecord.resource_group,
            func.sum(BillingRecord.pre_tax_cost).label("current_daily"),
        )
        .where(BillingRecord.usage_date == check_date)
        .group_by(BillingRecord.service_name, BillingRecord.resource_group)
    )
    current_rows = (await session.execute(current_stmt)).all()

    # Build baseline lookup dict: (service_name, resource_group) -> baseline_avg
    baseline_lookup: dict[tuple[str, str], float] = {
        (r.service_name, r.resource_group): float(r.baseline_avg_daily) for r in baseline_rows
    }

    # Step 5–8: Compare each pair to baseline; flag anomalies
    still_active: set[tuple[str, str]] = set()

    for row in current_rows:
        key = (row.service_name, row.resource_group)
        baseline_avg = baseline_lookup.get(key, 0.0)
        current = float(row.current_daily)

        # Skip if no baseline or zero baseline (can't compute deviation)
        if baseline_avg <= 0:
            continue

        pct_deviation = (current - baseline_avg) / baseline_avg * 100

        # Skip if deviation below 20% threshold
        if pct_deviation < 20.0:
            continue

        # Compute estimated monthly impact (excess × 30)
        estimated_monthly_impact = (current - baseline_avg) * 30

        # Skip if below $100 noise floor
        if estimated_monthly_impact < 100:
            continue

        # Classify severity by estimated monthly impact
        if estimated_monthly_impact >= 1000:
            severity = "critical"
        elif estimated_monthly_impact >= 500:
            severity = "high"
        else:
            severity = "medium"

        description = f"Spend increased {pct_deviation:.0f}% in {row.resource_group}"

        await upsert_anomaly(
            session,
            service_name=row.service_name,
            resource_group=row.resource_group,
            detected_date=check_date,
            baseline_daily_avg=baseline_avg,
            current_daily_cost=current,
            pct_deviation=pct_deviation,
            estimated_monthly_impact=estimated_monthly_impact,
            severity=severity,
            description=description,
        )
        still_active.add(key)

    logger.info(
        "run_anomaly_detection: detected %d anomalies on %s",
        len(still_active),
        check_date,
    )

    # Auto-resolve anomalies that are no longer triggered
    await auto_resolve_anomalies(session, still_active, check_date)

    # Commit all changes once
    await session.commit()

    # Dispatch notifications for anomalies that are new to this run
    newly_detected = still_active - existing_open
    if newly_detected:
        await _notify_new_anomalies(session, check_date, newly_detected)
        await session.commit()


# ---------------------------------------------------------------------------
# Anomaly notification helper
# ---------------------------------------------------------------------------


async def _notify_new_anomalies(
    session: AsyncSession,
    check_date: date,
    newly_detected: set[tuple[str, str]],
) -> None:
    """Dispatch notifications for anomalies that were first detected in this run.

    Queries the just-committed Anomaly rows and calls notify_anomaly_detected
    for each one. Errors on individual notifications are logged but do not
    abort the loop.
    """
    if not newly_detected:
        return

    keys = list(newly_detected)
    for service_name, resource_group in keys:
        stmt = select(Anomaly).where(
            Anomaly.service_name == service_name,
            Anomaly.resource_group == resource_group,
            Anomaly.detected_date == check_date,
        )
        anomaly = (await session.execute(stmt)).scalar_one_or_none()
        if anomaly is None:
            continue
        try:
            await notify_anomaly_detected(
                session,
                anomaly_id=anomaly.id,
                service_name=anomaly.service_name,
                resource_group=anomaly.resource_group,
                severity=anomaly.severity,
                pct_deviation=float(anomaly.pct_deviation),
                estimated_monthly_impact=float(anomaly.estimated_monthly_impact),
                baseline_daily_avg=float(anomaly.baseline_daily_avg),
                current_daily_cost=float(anomaly.current_daily_cost),
                detected_date=str(anomaly.detected_date),
            )
        except Exception as exc:
            logger.error(
                "_notify_new_anomalies: notification failed for %s/%s: %s",
                service_name,
                resource_group,
                exc,
            )


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------


async def upsert_anomaly(
    session: AsyncSession,
    *,
    service_name: str,
    resource_group: str,
    detected_date: date,
    baseline_daily_avg: float,
    current_daily_cost: float,
    pct_deviation: float,
    estimated_monthly_impact: float,
    severity: str,
    description: str,
) -> None:
    """Idempotently insert or update an anomaly record.

    On conflict on (service_name, resource_group, detected_date), updates
    metric columns but does NOT overwrite status or expected (preserves user
    actions such as dismiss/investigate).

    Caller is responsible for committing the session.
    """
    now = datetime.now(UTC)
    stmt = pg_insert(Anomaly).values(
        service_name=service_name,
        resource_group=resource_group,
        detected_date=detected_date,
        baseline_daily_avg=baseline_daily_avg,
        current_daily_cost=current_daily_cost,
        pct_deviation=pct_deviation,
        estimated_monthly_impact=estimated_monthly_impact,
        severity=severity,
        description=description,
        created_at=now,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["service_name", "resource_group", "detected_date"],
        set_={
            # Update detection metrics (spike may have changed in magnitude)
            "baseline_daily_avg": stmt.excluded.baseline_daily_avg,
            "current_daily_cost": stmt.excluded.current_daily_cost,
            "pct_deviation": stmt.excluded.pct_deviation,
            "estimated_monthly_impact": stmt.excluded.estimated_monthly_impact,
            "severity": stmt.excluded.severity,
            "description": stmt.excluded.description,
            "updated_at": stmt.excluded.updated_at,
            # Do NOT update: status, expected — preserve user actions
        },
    )
    await session.execute(stmt)


# ---------------------------------------------------------------------------
# Auto-resolve
# ---------------------------------------------------------------------------


async def auto_resolve_anomalies(
    session: AsyncSession,
    still_active: set[tuple[str, str]],
    check_date: date,
) -> None:
    """Mark open anomalies as resolved if their condition is no longer present.

    Queries open (new/investigating) anomalies for check_date that are not
    marked as expected, then resolves any whose (service_name, resource_group)
    pair is not in the still_active set (spike has passed).

    Caller is responsible for committing the session.
    """
    stmt = select(Anomaly).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.detected_date == check_date,
        Anomaly.expected == False,  # noqa: E712
    )
    open_anomalies = (await session.execute(stmt)).scalars().all()

    resolved_count = 0
    for anomaly in open_anomalies:
        key = (anomaly.service_name, anomaly.resource_group)
        if key not in still_active:
            anomaly.status = "resolved"
            anomaly.updated_at = datetime.now(UTC)
            resolved_count += 1

    if resolved_count:
        logger.info(
            "auto_resolve_anomalies: resolved %d anomaly(ies) on %s",
            resolved_count,
            check_date,
        )


# ---------------------------------------------------------------------------
# CRUD query helpers
# ---------------------------------------------------------------------------


async def get_anomalies(
    session: AsyncSession,
    *,
    status: str | None = None,
    severity: str | None = None,
    service_name: str | None = None,
    resource_group: str | None = None,
) -> list:
    """Return anomaly rows with optional filters.

    No default status filter — returns full history (new, investigating,
    resolved, dismissed) so the UI can show browsable history.
    Ordered by detected_date DESC, then estimated_monthly_impact DESC.
    """
    stmt = select(Anomaly)

    if status is not None:
        stmt = stmt.where(Anomaly.status == status)
    if severity is not None:
        stmt = stmt.where(Anomaly.severity == severity)
    if service_name is not None:
        stmt = stmt.where(Anomaly.service_name == service_name)
    if resource_group is not None:
        stmt = stmt.where(Anomaly.resource_group == resource_group)

    stmt = stmt.order_by(
        Anomaly.detected_date.desc(),
        Anomaly.estimated_monthly_impact.desc(),
    )

    result = await session.execute(stmt)
    return result.scalars().all()


async def get_anomaly_summary(session: AsyncSession) -> dict:
    """Compute KPI summary counts for the anomaly dashboard.

    Returns a dict with:
    - active_count: anomalies with status in (new, investigating) and expected=False
    - critical_count: active anomalies with severity='critical'
    - high_count: active anomalies with severity='high'
    - medium_count: active anomalies with severity='medium'
    - total_potential_impact: sum of estimated_monthly_impact for active anomalies
    - resolved_this_month: anomalies resolved in the current calendar month
    - detection_accuracy: (total_detected - expected_count) / total_detected * 100
      or None if total_detected == 0
    """
    today = date.today()

    # Active count: status in ('new', 'investigating') and not expected
    active_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.expected == False,  # noqa: E712
    )
    active_count = int((await session.execute(active_stmt)).scalar() or 0)

    # Critical count: active + severity='critical'
    critical_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.expected == False,  # noqa: E712
        Anomaly.severity == "critical",
    )
    critical_count = int((await session.execute(critical_stmt)).scalar() or 0)

    # High count: active + severity='high'
    high_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.expected == False,  # noqa: E712
        Anomaly.severity == "high",
    )
    high_count = int((await session.execute(high_stmt)).scalar() or 0)

    # Medium count: active + severity='medium'
    medium_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.expected == False,  # noqa: E712
        Anomaly.severity == "medium",
    )
    medium_count = int((await session.execute(medium_stmt)).scalar() or 0)

    # Total potential impact: sum of estimated_monthly_impact for active anomalies
    impact_stmt = select(func.sum(Anomaly.estimated_monthly_impact)).where(
        Anomaly.status.in_(["new", "investigating"]),
        Anomaly.expected == False,  # noqa: E712
    )
    total_potential_impact = float((await session.execute(impact_stmt)).scalar() or 0.0)

    # Resolved this month: status='resolved' and updated_at in current calendar month
    resolved_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status == "resolved",
        func.extract("year", Anomaly.updated_at) == today.year,
        func.extract("month", Anomaly.updated_at) == today.month,
    )
    resolved_this_month = int((await session.execute(resolved_stmt)).scalar() or 0)

    # Detection accuracy: (total_non_dismissed - expected_count) / total_non_dismissed * 100
    # total_detected = all anomalies that are not dismissed
    total_detected_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.status != "dismissed",
    )
    total_detected = int((await session.execute(total_detected_stmt)).scalar() or 0)

    expected_count_stmt = select(func.count(Anomaly.id)).where(
        Anomaly.expected == True,  # noqa: E712
    )
    expected_count = int((await session.execute(expected_count_stmt)).scalar() or 0)

    if total_detected > 0:
        detection_accuracy: float | None = (total_detected - expected_count) / total_detected * 100
    else:
        detection_accuracy = None

    return {
        "active_count": active_count,
        "critical_count": critical_count,
        "high_count": high_count,
        "medium_count": medium_count,
        "total_potential_impact": total_potential_impact,
        "resolved_this_month": resolved_this_month,
        "detection_accuracy": detection_accuracy,
    }


async def update_anomaly_status(
    session: AsyncSession,
    anomaly_id: uuid.UUID,
    new_status: str,
) -> Anomaly | None:
    """Update an anomaly's status and commit.

    Returns the updated Anomaly object, or None if not found.
    """
    stmt = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await session.execute(stmt)
    anomaly = result.scalar_one_or_none()

    if anomaly is None:
        return None

    anomaly.status = new_status
    anomaly.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(anomaly)
    return anomaly


async def mark_anomaly_expected(
    session: AsyncSession,
    anomaly_id: uuid.UUID,
) -> Anomaly | None:
    """Mark an anomaly as expected (false positive) and dismiss it.

    Sets expected=True and status='dismissed'. Returns the updated Anomaly
    object, or None if not found.
    """
    stmt = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await session.execute(stmt)
    anomaly = result.scalar_one_or_none()

    if anomaly is None:
        return None

    anomaly.expected = True
    anomaly.status = "dismissed"
    anomaly.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(anomaly)
    return anomaly


async def unmark_anomaly_expected(
    session: AsyncSession,
    anomaly_id: uuid.UUID,
) -> Anomaly | None:
    """Clear the expected flag and reset status to 'new'.

    Sets expected=False and status='new'. Returns the updated Anomaly
    object, or None if not found.
    """
    stmt = select(Anomaly).where(Anomaly.id == anomaly_id)
    result = await session.execute(stmt)
    anomaly = result.scalar_one_or_none()

    if anomaly is None:
        return None

    anomaly.expected = False
    anomaly.status = "new"
    anomaly.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(anomaly)
    return anomaly


async def get_anomalies_for_export(
    session: AsyncSession,
    *,
    severity: str | None = None,
    service_name: str | None = None,
) -> list:
    """Return all anomaly rows for CSV export.

    Applies optional severity and service_name filters.
    Same ordering as get_anomalies: detected_date DESC, estimated_monthly_impact DESC.
    """
    return await get_anomalies(
        session,
        severity=severity,
        service_name=service_name,
    )
