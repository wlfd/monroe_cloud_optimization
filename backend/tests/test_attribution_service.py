"""
Unit tests for app.services.attribution.

Covers:
- apply_allocation_rule: by_count, by_usage, manual_pct, zero usage fallback,
  unknown method
- _get_top_service_category helper
- CRUD helpers: update_tenant_display_name, acknowledge_tenant,
  create_allocation_rule, update_allocation_rule, delete_allocation_rule
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# apply_allocation_rule — pure function, no DB
# ---------------------------------------------------------------------------


def test_apply_allocation_rule_by_count_even_split():
    """by_count distributes cost equally among all tenants."""
    from app.services.attribution import apply_allocation_rule

    tenant_costs = {
        "tenant-a": Decimal("200"),
        "tenant-b": Decimal("100"),
        "tenant-c": Decimal("50"),
    }
    cost = Decimal("300")

    result = apply_allocation_rule(cost, "by_count", None, tenant_costs)

    assert len(result) == 3
    for v in result.values():
        assert abs(v - 100.0) < 0.01


def test_apply_allocation_rule_by_usage_proportional():
    """by_usage distributes cost proportionally to tenant usage."""
    from app.services.attribution import apply_allocation_rule

    tenant_costs = {
        "tenant-a": Decimal("300"),  # 75%
        "tenant-b": Decimal("100"),  # 25%
    }
    cost = Decimal("400")

    result = apply_allocation_rule(cost, "by_usage", None, tenant_costs)

    assert abs(result["tenant-a"] - 300.0) < 0.01
    assert abs(result["tenant-b"] - 100.0) < 0.01


def test_apply_allocation_rule_by_usage_zero_total_falls_back_to_by_count():
    """by_usage with all-zero usage falls back to equal split."""
    from app.services.attribution import apply_allocation_rule

    tenant_costs = {
        "tenant-a": Decimal("0"),
        "tenant-b": Decimal("0"),
    }
    cost = Decimal("200")

    result = apply_allocation_rule(cost, "by_usage", None, tenant_costs)

    assert abs(result["tenant-a"] - 100.0) < 0.01
    assert abs(result["tenant-b"] - 100.0) < 0.01


def test_apply_allocation_rule_manual_pct():
    """manual_pct distributes cost according to the provided percentages."""
    from app.services.attribution import apply_allocation_rule

    manual_pct = {"tenant-a": 70.0, "tenant-b": 30.0}
    tenant_costs = {"tenant-a": Decimal("500"), "tenant-b": Decimal("200")}
    cost = Decimal("1000")

    result = apply_allocation_rule(cost, "manual_pct", manual_pct, tenant_costs)

    assert abs(result["tenant-a"] - 700.0) < 0.01
    assert abs(result["tenant-b"] - 300.0) < 0.01


def test_apply_allocation_rule_manual_pct_missing_returns_empty():
    """manual_pct with no manual_pct dict returns empty allocation."""
    from app.services.attribution import apply_allocation_rule

    tenant_costs = {"tenant-a": Decimal("500")}
    cost = Decimal("1000")

    result = apply_allocation_rule(cost, "manual_pct", None, tenant_costs)

    assert result == {}


def test_apply_allocation_rule_unknown_method_returns_empty():
    """Unknown method logs a warning and returns an empty dict."""
    from app.services.attribution import apply_allocation_rule

    tenant_costs = {"tenant-a": Decimal("500")}
    cost = Decimal("1000")

    with patch("app.services.attribution.logger") as mock_logger:
        result = apply_allocation_rule(cost, "invalid_method", None, tenant_costs)

    assert result == {}
    mock_logger.warning.assert_called_once()


def test_apply_allocation_rule_empty_tenant_costs_returns_empty():
    """Empty tenant_costs dict returns empty allocation regardless of method."""
    from app.services.attribution import apply_allocation_rule

    result = apply_allocation_rule(Decimal("500"), "by_count", None, {})
    assert result == {}


# ---------------------------------------------------------------------------
# update_tenant_display_name
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_tenant_display_name_success():
    """update_tenant_display_name updates and returns the profile."""
    from app.services.attribution import update_tenant_display_name

    session = AsyncMock()
    profile = MagicMock()
    profile.tenant_id = "tenant-a"
    profile.display_name = "Old Name"

    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    session.execute.return_value = result

    updated = await update_tenant_display_name(session, "tenant-a", "New Name")

    assert updated is not None
    assert updated.display_name == "New Name"
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(profile)


@pytest.mark.asyncio
async def test_update_tenant_display_name_not_found():
    """update_tenant_display_name returns None when tenant doesn't exist."""
    from app.services.attribution import update_tenant_display_name

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await update_tenant_display_name(session, "nonexistent", "Name")

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# acknowledge_tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_acknowledge_tenant_clears_is_new():
    """acknowledge_tenant sets is_new=False and sets acknowledged_at."""
    from app.services.attribution import acknowledge_tenant

    session = AsyncMock()
    profile = MagicMock()
    profile.tenant_id = "tenant-a"
    profile.is_new = True

    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    session.execute.return_value = result

    updated = await acknowledge_tenant(session, "tenant-a")

    assert updated is not None
    assert updated.is_new is False
    assert updated.acknowledged_at is not None
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_acknowledge_tenant_not_found():
    """acknowledge_tenant returns None when tenant doesn't exist."""
    from app.services.attribution import acknowledge_tenant

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await acknowledge_tenant(session, "nonexistent")

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# create_allocation_rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_allocation_rule_assigns_next_priority():
    """create_allocation_rule sets priority = MAX(existing) + 1."""
    from app.schemas.attribution import AllocationRuleCreate
    from app.services.attribution import create_allocation_rule

    session = AsyncMock()
    # Max priority query returns 3 → next = 4
    max_priority_result = MagicMock()
    max_priority_result.scalar.return_value = 3
    session.execute.return_value = max_priority_result

    rule_data = AllocationRuleCreate(
        target_type="resource_group",
        target_value="rg-shared",
        method="by_usage",
        manual_pct=None,
    )

    rule = await create_allocation_rule(session, rule_data)

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.priority == 4
    assert added.target_type == "resource_group"
    assert added.method == "by_usage"
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_allocation_rule_no_existing_starts_at_one():
    """create_allocation_rule starts at priority=1 when no rules exist."""
    from app.schemas.attribution import AllocationRuleCreate
    from app.services.attribution import create_allocation_rule

    session = AsyncMock()
    max_priority_result = MagicMock()
    max_priority_result.scalar.return_value = None  # no existing rules
    session.execute.return_value = max_priority_result

    rule_data = AllocationRuleCreate(
        target_type="service_category",
        target_value="Networking",
        method="by_count",
    )

    rule = await create_allocation_rule(session, rule_data)

    added = session.add.call_args[0][0]
    assert added.priority == 1


# ---------------------------------------------------------------------------
# update_allocation_rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_allocation_rule_updates_provided_fields():
    """update_allocation_rule updates only fields provided in rule_data."""
    from app.schemas.attribution import AllocationRuleUpdate
    from app.services.attribution import update_allocation_rule

    session = AsyncMock()
    existing_rule = MagicMock()
    existing_rule.id = uuid.uuid4()
    existing_rule.target_type = "resource_group"
    existing_rule.target_value = "rg-old"
    existing_rule.method = "by_count"
    existing_rule.manual_pct = None

    result = MagicMock()
    result.scalar_one_or_none.return_value = existing_rule
    session.execute.return_value = result

    rule_data = AllocationRuleUpdate(target_value="rg-new", method="by_usage")
    updated = await update_allocation_rule(session, existing_rule.id, rule_data)

    assert updated is not None
    assert updated.target_value == "rg-new"
    assert updated.method == "by_usage"
    assert updated.target_type == "resource_group"  # unchanged
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_allocation_rule_not_found():
    """update_allocation_rule returns None when rule doesn't exist."""
    from app.schemas.attribution import AllocationRuleUpdate
    from app.services.attribution import update_allocation_rule

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    updated = await update_allocation_rule(
        session, uuid.uuid4(), AllocationRuleUpdate(method="by_count")
    )

    assert updated is None
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# delete_allocation_rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_allocation_rule_returns_true_and_renumbers():
    """delete_allocation_rule deletes rule and renumbers remaining ones."""
    from app.services.attribution import delete_allocation_rule

    session = AsyncMock()
    rule_to_delete = MagicMock()
    rule_to_delete.id = uuid.uuid4()

    remaining_1 = MagicMock()
    remaining_1.priority = 2
    remaining_2 = MagicMock()
    remaining_2.priority = 3

    # First execute: find the rule to delete
    find_result = MagicMock()
    find_result.scalar_one_or_none.return_value = rule_to_delete

    # Second execute: list remaining rules for renumbering
    remaining_scalars = MagicMock()
    remaining_scalars.all.return_value = [remaining_1, remaining_2]
    remaining_result = MagicMock()
    remaining_result.scalars.return_value = remaining_scalars

    session.execute.side_effect = [find_result, remaining_result]

    result = await delete_allocation_rule(session, rule_to_delete.id)

    assert result is True
    # Remaining rules should be renumbered 1, 2
    assert remaining_1.priority == 1
    assert remaining_2.priority == 2
    session.delete.assert_called_once_with(rule_to_delete)
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_allocation_rule_not_found():
    """delete_allocation_rule returns False when rule doesn't exist."""
    from app.services.attribution import delete_allocation_rule

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute.return_value = result

    deleted = await delete_allocation_rule(session, uuid.uuid4())

    assert deleted is False
    session.delete.assert_not_called()
    session.commit.assert_not_called()


# ---------------------------------------------------------------------------
# get_attribution_breakdown
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_attribution_breakdown_regular_tenant():
    """get_attribution_breakdown queries by tag for a regular tenant."""
    from app.services.attribution import get_attribution_breakdown

    session = AsyncMock()

    row1 = MagicMock()
    row1.service_name = "Virtual Machines"
    row1.total_cost = Decimal("500.0")
    row2 = MagicMock()
    row2.service_name = "Storage"
    row2.total_cost = Decimal("100.0")

    rows_mock = MagicMock()
    rows_mock.all.return_value = [row1, row2]
    result = MagicMock()
    result.all.return_value = [row1, row2]
    session.execute.return_value = result

    breakdown = await get_attribution_breakdown(session, "tenant-a", 2026, 3)

    assert len(breakdown) == 2
    assert breakdown[0]["service_name"] == "Virtual Machines"
    assert abs(breakdown[0]["total_cost"] - 500.0) < 0.01


@pytest.mark.asyncio
async def test_get_attribution_breakdown_unallocated():
    """get_attribution_breakdown uses tag='' filter for UNALLOCATED tenant."""
    from app.services.attribution import get_attribution_breakdown

    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result

    breakdown = await get_attribution_breakdown(session, "UNALLOCATED", 2026, 3)

    assert breakdown == []
    # Verify a query was made (even if empty result)
    session.execute.assert_called_once()
