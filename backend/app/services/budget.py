"""Budget management and threshold alerting service.

Provides CRUD for budgets and thresholds, current-period spend calculation,
and the check_budget_thresholds() scheduled job that fires AlertEvent rows
and dispatches notifications when thresholds are crossed.
"""

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.billing import BillingRecord
from app.models.budget import AlertEvent, Budget, BudgetThreshold
from app.models.notification import NotificationChannel
from app.services.notification import notify_budget_alert

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Billing-period helpers
# ---------------------------------------------------------------------------


def _current_period(period: str) -> str:
    """Return the current billing-period key for a budget.

    Monthly → 'YYYY-MM' (e.g. '2026-03')
    Annual  → 'YYYY'    (e.g. '2026')
    """
    today = date.today()
    if period == "monthly":
        return f"{today.year}-{today.month:02d}"
    return str(today.year)


def _period_date_range(period: str) -> tuple[date, date]:
    """Return (start_inclusive, end_exclusive) for the current billing period."""
    today = date.today()
    if period == "monthly":
        start = date(today.year, today.month, 1)
        if today.month == 12:
            end = date(today.year + 1, 1, 1)
        else:
            end = date(today.year, today.month + 1, 1)
    else:  # annual
        start = date(today.year, 1, 1)
        end = date(today.year + 1, 1, 1)
    return start, end


# ---------------------------------------------------------------------------
# Spend calculation
# ---------------------------------------------------------------------------


async def get_current_period_spend(session: AsyncSession, budget: Budget) -> Decimal:
    """Sum billing_records for the current billing period matching budget scope."""
    start, end = _period_date_range(budget.period)

    stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
        BillingRecord.usage_date >= start,
        BillingRecord.usage_date < end,
    )

    if budget.scope_type == "resource_group" and budget.scope_value:
        stmt = stmt.where(BillingRecord.resource_group == budget.scope_value)
    elif budget.scope_type == "service" and budget.scope_value:
        stmt = stmt.where(BillingRecord.service_name == budget.scope_value)
    elif budget.scope_type == "tag" and budget.scope_value:
        stmt = stmt.where(BillingRecord.tag == budget.scope_value)
    # 'subscription' scope = no additional filter (single-subscription setup)

    result = await session.execute(stmt)
    return result.scalar() or Decimal("0")


# ---------------------------------------------------------------------------
# Budget CRUD
# ---------------------------------------------------------------------------


async def create_budget(
    session: AsyncSession,
    *,
    name: str,
    scope_type: str,
    scope_value: str | None,
    amount_usd: Decimal,
    period: str,
    start_date: date,
    end_date: date | None,
    created_by: uuid.UUID | None,
) -> Budget:
    """Create a new Budget row with the given parameters and commit."""
    budget = Budget(
        name=name,
        scope_type=scope_type,
        scope_value=scope_value,
        amount_usd=amount_usd,
        period=period,
        start_date=start_date,
        end_date=end_date,
        created_by=created_by,
    )
    session.add(budget)
    await session.commit()
    await session.refresh(budget)
    return budget


async def get_budgets(session: AsyncSession) -> list[Budget]:
    """Return all active budgets ordered by created_at descending."""
    stmt = select(Budget).where(Budget.is_active == True).order_by(Budget.created_at.desc())  # noqa: E712
    return (await session.execute(stmt)).scalars().all()


async def get_budget(session: AsyncSession, budget_id: uuid.UUID) -> Budget | None:
    """Retrieve a single Budget by primary key, or None if not found."""
    stmt = select(Budget).where(Budget.id == budget_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_budget(
    session: AsyncSession,
    budget_id: uuid.UUID,
    *,
    name: str | None = None,
    amount_usd: Decimal | None = None,
    end_date: date | None = None,
) -> Budget | None:
    """Patch name, amount_usd, or end_date on an existing budget."""
    budget = await get_budget(session, budget_id)
    if budget is None:
        return None
    if name is not None:
        budget.name = name
    if amount_usd is not None:
        budget.amount_usd = amount_usd
    if end_date is not None:
        budget.end_date = end_date
    budget.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(budget)
    return budget


async def deactivate_budget(session: AsyncSession, budget_id: uuid.UUID) -> Budget | None:
    """Soft-delete: set is_active=False. History is preserved."""
    budget = await get_budget(session, budget_id)
    if budget is None:
        return None
    budget.is_active = False
    budget.updated_at = datetime.now(UTC)
    await session.commit()
    return budget


# ---------------------------------------------------------------------------
# Threshold CRUD
# ---------------------------------------------------------------------------


async def add_threshold(
    session: AsyncSession,
    budget_id: uuid.UUID,
    *,
    threshold_percent: int,
    notification_channel_id: uuid.UUID | None,
) -> BudgetThreshold | None:
    """Add a threshold to a budget. Returns None if the budget does not exist."""
    budget = await get_budget(session, budget_id)
    if budget is None:
        return None
    threshold = BudgetThreshold(
        budget_id=budget_id,
        threshold_percent=threshold_percent,
        notification_channel_id=notification_channel_id,
    )
    session.add(threshold)
    await session.commit()
    await session.refresh(threshold)
    return threshold


async def remove_threshold(
    session: AsyncSession, threshold_id: uuid.UUID, budget_id: uuid.UUID | None = None
) -> bool:
    """Delete a threshold by ID. Returns True if found and deleted.

    If budget_id is provided, also verifies the threshold belongs to that budget.
    Returns False (resulting in 404) if the threshold does not belong to the budget.
    """
    stmt = select(BudgetThreshold).where(BudgetThreshold.id == threshold_id)
    threshold = (await session.execute(stmt)).scalar_one_or_none()
    if threshold is None:
        return False
    if budget_id is not None and threshold.budget_id != budget_id:
        return False
    await session.delete(threshold)
    await session.commit()
    return True


async def get_thresholds(session: AsyncSession, budget_id: uuid.UUID) -> list[BudgetThreshold]:
    """Return all BudgetThreshold rows for a budget ordered by threshold_percent."""
    stmt = (
        select(BudgetThreshold)
        .where(BudgetThreshold.budget_id == budget_id)
        .order_by(BudgetThreshold.threshold_percent)
    )
    return (await session.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# Alert event query
# ---------------------------------------------------------------------------


async def get_alert_events(session: AsyncSession, budget_id: uuid.UUID) -> list[AlertEvent]:
    """Return all AlertEvent rows for a budget ordered by triggered_at descending."""
    stmt = (
        select(AlertEvent)
        .where(AlertEvent.budget_id == budget_id)
        .order_by(AlertEvent.triggered_at.desc())
    )
    return (await session.execute(stmt)).scalars().all()


# ---------------------------------------------------------------------------
# Scheduled threshold check job
# ---------------------------------------------------------------------------


async def check_budget_thresholds() -> None:
    """Evaluate all active budgets against current-period spend.

    For each threshold that has been crossed and has not already fired this
    billing period: create an AlertEvent, update the threshold's
    last_triggered_period, and dispatch a notification to the linked channel.

    Called by the APScheduler job every 4 hours (60 min after ingestion).
    Manages its own DB session.
    """
    async with AsyncSessionLocal() as session:
        budgets_stmt = select(Budget).where(Budget.is_active == True)  # noqa: E712
        budgets: list[Budget] = (await session.execute(budgets_stmt)).scalars().all()

        if not budgets:
            logger.info("check_budget_thresholds: no active budgets")
            return

        logger.info("check_budget_thresholds: checking %d budget(s)", len(budgets))

        for budget in budgets:
            async with AsyncSessionLocal() as budget_session:
                try:
                    await _check_one_budget(budget_session, budget)
                except Exception as exc:
                    logger.error(
                        "check_budget_thresholds: budget %s (%s) failed: %s",
                        budget.id,
                        budget.name,
                        exc,
                    )
                    await budget_session.rollback()

        logger.info("check_budget_thresholds: done")


async def _check_one_budget(session: AsyncSession, budget: Budget) -> None:
    """Evaluate one budget's thresholds against current spend and dispatch notifications."""
    current_spend = await get_current_period_spend(session, budget)
    if budget.amount_usd <= 0:
        return

    spend_pct = current_spend / budget.amount_usd * 100
    current_period = _current_period(budget.period)

    thresholds_stmt = (
        select(BudgetThreshold)
        .where(BudgetThreshold.budget_id == budget.id)
        .order_by(BudgetThreshold.threshold_percent)
    )
    thresholds: list[BudgetThreshold] = (await session.execute(thresholds_stmt)).scalars().all()

    for threshold in thresholds:
        if spend_pct < threshold.threshold_percent:
            continue
        if threshold.last_triggered_period == current_period:
            continue  # Already fired this threshold in the current billing period

        # Create the alert event
        event = AlertEvent(
            budget_id=budget.id,
            threshold_id=threshold.id,
            billing_period=current_period,
            spend_at_trigger=current_spend,
            budget_amount=budget.amount_usd,
            threshold_percent=threshold.threshold_percent,
            delivery_status="pending",
        )
        session.add(event)
        await session.flush()  # Populate event.id before passing to notification

        # Mark threshold as fired for this period
        threshold.last_triggered_at = datetime.now(UTC)
        threshold.last_triggered_period = current_period

        # Dispatch notification if a channel is linked
        final_status = "no_channel"
        if threshold.notification_channel_id is not None:
            channel_stmt = select(NotificationChannel).where(
                NotificationChannel.id == threshold.notification_channel_id,
                NotificationChannel.is_active == True,  # noqa: E712
            )
            channel = (await session.execute(channel_stmt)).scalar_one_or_none()
            if channel:
                try:
                    delivery = await notify_budget_alert(
                        session,
                        alert_event_id=event.id,
                        channel=channel,
                        budget_name=budget.name,
                        scope_type=budget.scope_type,
                        scope_value=budget.scope_value,
                        threshold_percent=threshold.threshold_percent,
                        spend_at_trigger=float(current_spend),
                        budget_amount=float(budget.amount_usd),
                        billing_period=current_period,
                    )
                    final_status = delivery.status
                except Exception as exc:
                    logger.error(
                        "_check_one_budget: notification failed for budget %s threshold %d%%: %s",
                        budget.id,
                        threshold.threshold_percent,
                        exc,
                    )
                    final_status = "failed"

        event.delivery_status = final_status

        logger.info(
            "_check_one_budget: budget '%s' %d%% threshold fired (spend=%.2f/%.2f, period=%s, status=%s)",
            budget.name,
            threshold.threshold_percent,
            float(current_spend),
            float(budget.amount_usd),
            current_period,
            final_status,
        )

    await session.commit()
