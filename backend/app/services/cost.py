import calendar
from datetime import date, timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingRecord

DIMENSION_MAP = {
    "service_name": BillingRecord.service_name,
    "resource_group": BillingRecord.resource_group,
    "region": BillingRecord.region,
    "tag": BillingRecord.tag,
}


async def get_spend_summary(session: AsyncSession) -> dict:
    """Compute MTD total, end-of-month projection, prior month total, and MoM delta."""
    today = date.today()
    current_year = today.year
    current_month = today.month
    days_elapsed = today.day
    days_in_month = calendar.monthrange(current_year, current_month)[1]

    # MTD total
    mtd_stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
        extract("year", BillingRecord.usage_date) == current_year,
        extract("month", BillingRecord.usage_date) == current_month,
    )
    mtd_result = await session.execute(mtd_stmt)
    mtd_total = float(mtd_result.scalar() or 0.0)

    # Projection: (mtd / days_elapsed) * days_in_month
    if days_elapsed > 0:
        projected_month_end = (mtd_total / days_elapsed) * days_in_month
    else:
        projected_month_end = 0.0

    # Prior month (handle January -> December of prior year)
    if current_month == 1:
        prior_year = current_year - 1
        prior_month = 12
    else:
        prior_year = current_year
        prior_month = current_month - 1

    prior_stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
        extract("year", BillingRecord.usage_date) == prior_year,
        extract("month", BillingRecord.usage_date) == prior_month,
    )
    prior_result = await session.execute(prior_stmt)
    prior_month_total = float(prior_result.scalar() or 0.0)

    # MoM delta: ((mtd - prior) / prior * 100) if prior > 0 else None
    if prior_month_total > 0:
        mom_delta_pct = (mtd_total - prior_month_total) / prior_month_total * 100
    else:
        mom_delta_pct = None

    return {
        "mtd_total": mtd_total,
        "projected_month_end": projected_month_end,
        "prior_month_total": prior_month_total,
        "mom_delta_pct": mom_delta_pct,
    }


async def get_daily_spend(session: AsyncSession, days: int) -> list:
    """Return daily spend totals grouped by usage_date for the past N days."""
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            BillingRecord.usage_date,
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(BillingRecord.usage_date)
        .order_by(BillingRecord.usage_date.asc())
    )
    result = await session.execute(stmt)
    return result.all()


async def get_breakdown(session: AsyncSession, dimension: str, days: int) -> list:
    """Return spend breakdown grouped by the specified dimension for the past N days."""
    if dimension not in DIMENSION_MAP:
        raise ValueError(f"Invalid dimension: {dimension}")

    col = DIMENSION_MAP[dimension]
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            col.label("dimension_value"),
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(col)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
    )
    result = await session.execute(stmt)
    return result.all()


async def get_top_resources(session: AsyncSession, days: int) -> list:
    """Return top 10 resources by total cost for the past N days."""
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            BillingRecord.resource_id,
            BillingRecord.resource_name,
            BillingRecord.service_name,
            BillingRecord.resource_group,
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(
            BillingRecord.usage_date >= cutoff,
            BillingRecord.resource_id != "",
        )
        .group_by(
            BillingRecord.resource_id,
            BillingRecord.resource_name,
            BillingRecord.service_name,
            BillingRecord.resource_group,
        )
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
        .limit(10)
    )
    result = await session.execute(stmt)
    return result.all()


async def get_breakdown_for_export(session: AsyncSession, dimension: str, days: int) -> list:
    """Same as get_breakdown but without LIMIT — used for CSV export."""
    if dimension not in DIMENSION_MAP:
        raise ValueError(f"Invalid dimension: {dimension}")

    col = DIMENSION_MAP[dimension]
    cutoff = date.today() - timedelta(days=days)
    stmt = (
        select(
            col.label("dimension_value"),
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(BillingRecord.usage_date >= cutoff)
        .group_by(col)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
    )
    result = await session.execute(stmt)
    return result.all()
