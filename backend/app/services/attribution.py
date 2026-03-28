"""Attribution service.

Implements the daily attribution job, allocation rule engine, and CRUD helpers
for tenant profiles and allocation rules.

run_attribution() runs as a post-ingestion hook called from ingestion.py.
Uses AsyncSessionLocal directly (same pattern as ingestion.py — jobs run
outside request context).
"""

import calendar
import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.attribution import AllocationRule, TenantAttribution, TenantProfile
from app.models.billing import BillingRecord
from app.schemas.attribution import AllocationRuleCreate, AllocationRuleUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Allocation math helper
# ---------------------------------------------------------------------------


def apply_allocation_rule(
    cost: Decimal,
    method: str,
    manual_pct: dict | None,
    tenant_costs: dict[str, Decimal],
) -> dict[str, float]:
    """Distribute `cost` among tenants according to `method`.

    Returns a dict of {tenant_id: allocated_amount}.
    """
    if not tenant_costs:
        return {}

    if method == "by_count":
        per_tenant = float(cost) / len(tenant_costs)
        return dict.fromkeys(tenant_costs, per_tenant)

    if method == "by_usage":
        total_usage = sum(tenant_costs.values())
        if total_usage == 0:
            # Fall back to by_count when all tagged costs are zero
            per_tenant = float(cost) / len(tenant_costs)
            return dict.fromkeys(tenant_costs, per_tenant)
        return {t: float(cost) * float(v) / float(total_usage) for t, v in tenant_costs.items()}

    if method == "manual_pct":
        if not manual_pct:
            return {}
        return {t: float(cost) * (pct / 100.0) for t, pct in manual_pct.items()}

    logger.warning("apply_allocation_rule: unknown method '%s' — skipping", method)
    return {}


# ---------------------------------------------------------------------------
# Daily attribution job
# ---------------------------------------------------------------------------


async def run_attribution() -> None:
    """Run the daily attribution job.

    Discovers tenants, computes tagged/untagged costs, applies allocation
    rules, and upserts TenantAttribution rows for the current billing period.

    Called from _do_ingestion() after anomaly detection.
    """
    async with AsyncSessionLocal() as session:
        # Step 2: Determine current year/month from MAX(usage_date)
        max_date_stmt = select(func.max(BillingRecord.usage_date))
        check_date: date | None = (await session.execute(max_date_stmt)).scalar()

        if check_date is None:
            logger.warning("run_attribution: billing_records table is empty — skipping")
            return

        year = check_date.year
        month = check_date.month
        today = date.today()

        logger.info("run_attribution: computing attribution for %d-%02d", year, month)

        # Step 3: Discover tenants — UPSERT into tenant_profiles
        distinct_tags_stmt = select(BillingRecord.tag).where(BillingRecord.tag != "").distinct()
        distinct_tags = (await session.execute(distinct_tags_stmt)).scalars().all()

        for tenant_id in distinct_tags:
            upsert_stmt = pg_insert(TenantProfile).values(
                tenant_id=tenant_id,
                is_new=True,
                first_seen=today,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            upsert_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=["tenant_id"],
                set_={
                    # On conflict: update updated_at but do NOT reset is_new
                    # (preserves acknowledged tenants)
                    "updated_at": upsert_stmt.excluded.updated_at,
                },
            )
            await session.execute(upsert_stmt)

        # Build date range for the period (inclusive on both ends)
        period_start = date(year, month, 1)
        period_end = date(year, month, calendar.monthrange(year, month)[1])

        # Step 4: Compute tagged costs per tenant for this year/month
        tagged_stmt = (
            select(BillingRecord.tag, func.sum(BillingRecord.pre_tax_cost).label("total"))
            .where(
                BillingRecord.tag != "",
                BillingRecord.usage_date >= period_start,
                BillingRecord.usage_date <= period_end,
            )
            .group_by(BillingRecord.tag)
        )
        tagged_rows = (await session.execute(tagged_stmt)).all()
        tagged_costs: dict[str, Decimal] = {row.tag: Decimal(str(row.total)) for row in tagged_rows}

        # Step 5: Compute total untagged cost for this year/month
        untagged_stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
            BillingRecord.tag == "",
            BillingRecord.usage_date >= period_start,
            BillingRecord.usage_date <= period_end,
        )
        untagged_total: Decimal = Decimal(str((await session.execute(untagged_stmt)).scalar() or 0))

        # Step 6: Load allocation rules ordered by priority
        rules_stmt = select(AllocationRule).order_by(AllocationRule.priority.asc())
        rules = (await session.execute(rules_stmt)).scalars().all()

        # Step 7: Apply allocation rules
        allocated_per_tenant: dict[str, float] = {}
        total_rule_matched = Decimal("0")

        for rule in rules:
            # Compute the subset of untagged cost matched by this rule
            if rule.target_type == "resource_group":
                rule_cost_stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
                    BillingRecord.tag == "",
                    BillingRecord.resource_group == rule.target_value,
                    BillingRecord.usage_date >= period_start,
                    BillingRecord.usage_date <= period_end,
                )
            elif rule.target_type == "service_category":
                rule_cost_stmt = select(func.sum(BillingRecord.pre_tax_cost)).where(
                    BillingRecord.tag == "",
                    BillingRecord.service_name == rule.target_value,
                    BillingRecord.usage_date >= period_start,
                    BillingRecord.usage_date <= period_end,
                )
            else:
                logger.warning(
                    "run_attribution: unknown rule target_type '%s' — skipping rule %s",
                    rule.target_type,
                    rule.id,
                )
                continue

            rule_cost_scalar = (await session.execute(rule_cost_stmt)).scalar()
            if not rule_cost_scalar:
                continue
            rule_cost = Decimal(str(rule_cost_scalar))

            allocations = apply_allocation_rule(
                rule_cost, rule.method, rule.manual_pct, tagged_costs
            )

            for tenant_id, amount in allocations.items():
                allocated_per_tenant[tenant_id] = allocated_per_tenant.get(tenant_id, 0.0) + amount
            total_rule_matched += rule_cost

        # Remaining unallocated cost
        unallocated = untagged_total - total_rule_matched
        if unallocated < 0:
            unallocated = Decimal("0")

        # Step 8: Compute totals per tenant (tagged + allocated)
        all_tenant_ids: set[str] = set(tagged_costs.keys()) | set(allocated_per_tenant.keys())

        total_per_tenant: dict[str, float] = {}
        for tenant_id in all_tenant_ids:
            tagged = float(tagged_costs.get(tenant_id, Decimal("0")))
            allocated = allocated_per_tenant.get(tenant_id, 0.0)
            total_per_tenant[tenant_id] = tagged + allocated

        if unallocated > 0:
            total_per_tenant["UNALLOCATED"] = float(unallocated)

        # Step 9: Compute grand total
        grand_total = sum(total_per_tenant.values())

        # Step 10: Fetch prior month totals for MoM delta
        if month == 1:
            prior_year, prior_month = year - 1, 12
        else:
            prior_year, prior_month = year, month - 1

        prior_stmt = select(TenantAttribution).where(
            TenantAttribution.year == prior_year,
            TenantAttribution.month == prior_month,
        )
        prior_rows = (await session.execute(prior_stmt)).scalars().all()
        prior_totals: dict[str, float] = {
            row.tenant_id: float(row.total_cost) for row in prior_rows
        }

        # Step 11: Upsert TenantAttribution rows
        computed_at = datetime.now(UTC)

        for tenant_id, total_cost in total_per_tenant.items():
            pct_of_total = (total_cost / grand_total * 100) if grand_total > 0 else 0.0
            mom_delta = total_cost - prior_totals[tenant_id] if tenant_id in prior_totals else None

            # Compute top_service_category for this tenant
            top_service_category = await _get_top_service_category(session, tenant_id, year, month)

            tagged_cost_val = float(tagged_costs.get(tenant_id, Decimal("0")))
            allocated_cost_val = allocated_per_tenant.get(tenant_id, 0.0)

            row_values = {
                "tenant_id": tenant_id,
                "year": year,
                "month": month,
                "total_cost": total_cost,
                "pct_of_total": round(pct_of_total, 4),
                "mom_delta_usd": mom_delta,
                "top_service_category": top_service_category,
                "allocated_cost": allocated_cost_val,
                "tagged_cost": tagged_cost_val,
                "computed_at": computed_at,
                "updated_at": computed_at,
            }

            upsert_stmt = pg_insert(TenantAttribution).values(**row_values)
            upsert_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=["tenant_id", "year", "month"],
                set_={
                    "total_cost": upsert_stmt.excluded.total_cost,
                    "pct_of_total": upsert_stmt.excluded.pct_of_total,
                    "mom_delta_usd": upsert_stmt.excluded.mom_delta_usd,
                    "top_service_category": upsert_stmt.excluded.top_service_category,
                    "allocated_cost": upsert_stmt.excluded.allocated_cost,
                    "tagged_cost": upsert_stmt.excluded.tagged_cost,
                    "computed_at": upsert_stmt.excluded.computed_at,
                    "updated_at": upsert_stmt.excluded.updated_at,
                },
            )
            await session.execute(upsert_stmt)

        await session.commit()
        logger.info(
            "run_attribution: committed %d attribution rows for %d-%02d",
            len(total_per_tenant),
            year,
            month,
        )


async def _get_top_service_category(
    session: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
) -> str | None:
    """Return the service_name with highest spend for the given tenant/period."""
    if tenant_id == "UNALLOCATED":
        tag_filter = BillingRecord.tag == ""
    else:
        tag_filter = BillingRecord.tag == tenant_id

    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])

    stmt = (
        select(BillingRecord.service_name, func.sum(BillingRecord.pre_tax_cost).label("svc_cost"))
        .where(
            tag_filter,
            BillingRecord.usage_date >= period_start,
            BillingRecord.usage_date <= period_end,
        )
        .group_by(BillingRecord.service_name)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    return row.service_name if row else None


# ---------------------------------------------------------------------------
# Query helpers for API layer
# ---------------------------------------------------------------------------


async def get_attributions(
    session: AsyncSession,
    year: int,
    month: int,
) -> list:
    """Return TenantAttribution rows for year/month, enriched with display_name.

    Performs a two-step query: fetch attributions, fetch profiles as dict,
    attach display_name in Python (TenantAttribution has no ORM relationship
    to TenantProfile).

    Returns list of objects with all TenantAttribution columns plus display_name.
    Ordered by total_cost DESC.
    """
    attr_stmt = (
        select(TenantAttribution)
        .where(
            TenantAttribution.year == year,
            TenantAttribution.month == month,
        )
        .order_by(TenantAttribution.total_cost.desc())
    )
    attributions = (await session.execute(attr_stmt)).scalars().all()

    if not attributions:
        return []

    # Fetch display names for all tenant_ids present
    tenant_ids = [a.tenant_id for a in attributions]
    profiles_stmt = select(TenantProfile).where(TenantProfile.tenant_id.in_(tenant_ids))
    profiles = (await session.execute(profiles_stmt)).scalars().all()
    display_name_map: dict[str, str | None] = {p.tenant_id: p.display_name for p in profiles}

    # Attach display_name as a dynamic attribute on each ORM row
    result = []
    for attr in attributions:
        # Wrap with a simple namespace that exposes display_name alongside ORM fields
        wrapped = _AttributionWithDisplayName(attr, display_name_map.get(attr.tenant_id))
        result.append(wrapped)

    return result


class _AttributionWithDisplayName:
    """Thin wrapper that exposes TenantAttribution fields + display_name.

    Needed because TenantAttribution has no ORM relationship to TenantProfile.
    Used only internally between service and API layer.
    """

    __slots__ = (
        "tenant_id",
        "display_name",
        "year",
        "month",
        "total_cost",
        "pct_of_total",
        "mom_delta_usd",
        "top_service_category",
        "allocated_cost",
        "tagged_cost",
        "computed_at",
    )

    def __init__(self, attr: TenantAttribution, display_name: str | None) -> None:
        self.tenant_id = attr.tenant_id
        self.display_name = display_name
        self.year = attr.year
        self.month = attr.month
        self.total_cost = float(attr.total_cost)
        self.pct_of_total = float(attr.pct_of_total)
        self.mom_delta_usd = float(attr.mom_delta_usd) if attr.mom_delta_usd is not None else None
        self.top_service_category = attr.top_service_category
        self.allocated_cost = float(attr.allocated_cost)
        self.tagged_cost = float(attr.tagged_cost)
        self.computed_at = attr.computed_at


async def get_attribution_breakdown(
    session: AsyncSession,
    tenant_id: str,
    year: int,
    month: int,
) -> list[dict]:
    """Return per-service cost breakdown for a tenant in a given period.

    Queries billing_records on-the-fly (fresh, not pre-computed).
    For UNALLOCATED, queries untagged records (tag='').
    """
    if tenant_id == "UNALLOCATED":
        tag_filter = BillingRecord.tag == ""
    else:
        tag_filter = BillingRecord.tag == tenant_id

    period_start = date(year, month, 1)
    period_end = date(year, month, calendar.monthrange(year, month)[1])

    stmt = (
        select(
            BillingRecord.service_name,
            func.sum(BillingRecord.pre_tax_cost).label("total_cost"),
        )
        .where(
            tag_filter,
            BillingRecord.usage_date >= period_start,
            BillingRecord.usage_date <= period_end,
        )
        .group_by(BillingRecord.service_name)
        .order_by(func.sum(BillingRecord.pre_tax_cost).desc())
    )
    rows = (await session.execute(stmt)).all()
    return [{"service_name": row.service_name, "total_cost": float(row.total_cost)} for row in rows]


# ---------------------------------------------------------------------------
# Settings CRUD helpers
# ---------------------------------------------------------------------------


async def list_tenant_profiles(session: AsyncSession) -> list:
    """Return all tenant profiles ordered by first_seen ASC."""
    stmt = select(TenantProfile).order_by(TenantProfile.first_seen.asc())
    return (await session.execute(stmt)).scalars().all()


async def update_tenant_display_name(
    session: AsyncSession,
    tenant_id: str,
    display_name: str,
) -> TenantProfile | None:
    """Update display_name for a tenant. Returns updated profile or None if not found."""
    stmt = select(TenantProfile).where(TenantProfile.tenant_id == tenant_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if profile is None:
        return None
    profile.display_name = display_name
    profile.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(profile)
    return profile


async def acknowledge_tenant(
    session: AsyncSession,
    tenant_id: str,
) -> TenantProfile | None:
    """Clear the is_new flag for a tenant. Returns updated profile or None if not found."""
    stmt = select(TenantProfile).where(TenantProfile.tenant_id == tenant_id)
    profile = (await session.execute(stmt)).scalar_one_or_none()
    if profile is None:
        return None
    profile.is_new = False
    profile.acknowledged_at = datetime.now(UTC)
    profile.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(profile)
    return profile


async def list_allocation_rules(session: AsyncSession) -> list:
    """Return all allocation rules ordered by priority ASC."""
    stmt = select(AllocationRule).order_by(AllocationRule.priority.asc())
    return (await session.execute(stmt)).scalars().all()


async def create_allocation_rule(
    session: AsyncSession,
    rule_data: AllocationRuleCreate,
) -> AllocationRule:
    """Create a new allocation rule with priority = MAX(priority) + 1."""
    max_priority_stmt = select(func.max(AllocationRule.priority))
    max_priority = (await session.execute(max_priority_stmt)).scalar()
    next_priority = (max_priority or 0) + 1

    rule = AllocationRule(
        priority=next_priority,
        target_type=rule_data.target_type,
        target_value=rule_data.target_value,
        method=rule_data.method,
        manual_pct=rule_data.manual_pct,
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    return rule


async def update_allocation_rule(
    session: AsyncSession,
    rule_id: uuid.UUID,
    rule_data: AllocationRuleUpdate,
) -> AllocationRule | None:
    """Update provided fields on an allocation rule. Returns updated rule or None if not found."""
    stmt = select(AllocationRule).where(AllocationRule.id == rule_id)
    rule = (await session.execute(stmt)).scalar_one_or_none()
    if rule is None:
        return None

    if rule_data.target_type is not None:
        rule.target_type = rule_data.target_type
    if rule_data.target_value is not None:
        rule.target_value = rule_data.target_value
    if rule_data.method is not None:
        rule.method = rule_data.method
    if rule_data.manual_pct is not None:
        rule.manual_pct = rule_data.manual_pct

    rule.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(rule)
    return rule


async def delete_allocation_rule(
    session: AsyncSession,
    rule_id: uuid.UUID,
) -> bool:
    """Delete an allocation rule and renumber remaining rules 1..N by current priority.

    Returns True if deleted, False if not found.
    """
    stmt = select(AllocationRule).where(AllocationRule.id == rule_id)
    rule = (await session.execute(stmt)).scalar_one_or_none()
    if rule is None:
        return False

    await session.delete(rule)
    await session.flush()

    # Renumber remaining rules sequentially
    remaining_stmt = select(AllocationRule).order_by(AllocationRule.priority.asc())
    remaining = (await session.execute(remaining_stmt)).scalars().all()
    for i, r in enumerate(remaining, start=1):
        r.priority = i
        r.updated_at = datetime.now(UTC)

    await session.commit()
    return True


async def reorder_allocation_rules(
    session: AsyncSession,
    rule_ids: list[uuid.UUID],
) -> list:
    """Renumber rules to match the provided order (1, 2, 3...).

    Returns the full updated rule list ordered by new priority.
    """
    for i, rule_id in enumerate(rule_ids, start=1):
        stmt = select(AllocationRule).where(AllocationRule.id == rule_id)
        rule = (await session.execute(stmt)).scalar_one_or_none()
        if rule is not None:
            rule.priority = i
            rule.updated_at = datetime.now(UTC)

    await session.commit()
    return await list_allocation_rules(session)
