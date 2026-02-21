"""Settings API router.

Provides 8 admin-only endpoints under /settings:
- GET  /settings/tenants                        — list all tenant profiles
- PATCH /settings/tenants/{tenant_id}/name      — update display name
- POST  /settings/tenants/{tenant_id}/acknowledge — clear is_new flag
- GET  /settings/rules                          — list rules ordered by priority
- POST  /settings/rules                         — create new rule
- PATCH /settings/rules/{rule_id}               — update rule
- DELETE /settings/rules/{rule_id}              — delete rule and renumber
- POST  /settings/rules/reorder                 — set new rule order

All endpoints require admin role (require_admin from api.v1.ingestion).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.ingestion import require_admin
from app.core.dependencies import get_db
from app.models.user import User
from app.schemas.attribution import (
    AllocationRuleCreate,
    AllocationRuleResponse,
    AllocationRuleUpdate,
    RuleReorderRequest,
    TenantDisplayNameUpdate,
    TenantProfileResponse,
)
from app.services.attribution import (
    acknowledge_tenant,
    create_allocation_rule,
    delete_allocation_rule,
    list_allocation_rules,
    list_tenant_profiles,
    reorder_allocation_rules,
    update_allocation_rule,
    update_tenant_display_name,
)

router = APIRouter(tags=["settings"])


# ---------------------------------------------------------------------------
# Tenant profile endpoints
# ---------------------------------------------------------------------------


@router.get("/tenants", response_model=list[TenantProfileResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all tenant profiles ordered by first_seen."""
    profiles = await list_tenant_profiles(db)
    return [TenantProfileResponse.model_validate(p) for p in profiles]


@router.patch("/tenants/{tenant_id}/name", response_model=TenantProfileResponse)
async def update_tenant_name(
    tenant_id: str,
    body: TenantDisplayNameUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update the display name for a tenant profile."""
    profile = await update_tenant_display_name(db, tenant_id, body.display_name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return TenantProfileResponse.model_validate(profile)


@router.post("/tenants/{tenant_id}/acknowledge")
async def acknowledge_tenant_endpoint(
    tenant_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Clear the is_new flag for a tenant (acknowledge new tenant discovery)."""
    profile = await acknowledge_tenant(db, tenant_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Tenant profile not found")
    return {"status": "acknowledged"}


# ---------------------------------------------------------------------------
# Allocation rule endpoints
# ---------------------------------------------------------------------------


@router.get("/rules", response_model=list[AllocationRuleResponse])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all allocation rules ordered by priority ASC."""
    rules = await list_allocation_rules(db)
    return [AllocationRuleResponse.model_validate(r) for r in rules]


@router.post("/rules", response_model=AllocationRuleResponse, status_code=201)
async def create_rule(
    body: AllocationRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Create a new allocation rule. Pydantic validates manual_pct sum."""
    rule = await create_allocation_rule(db, body)
    return AllocationRuleResponse.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=AllocationRuleResponse)
async def update_rule(
    rule_id: uuid.UUID,
    body: AllocationRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Update fields on an existing allocation rule."""
    rule = await update_allocation_rule(db, rule_id, body)
    if rule is None:
        raise HTTPException(status_code=404, detail="Allocation rule not found")
    return AllocationRuleResponse.model_validate(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(
    rule_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Delete an allocation rule and renumber remaining rules sequentially."""
    deleted = await delete_allocation_rule(db, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Allocation rule not found")
    return {"status": "deleted"}


@router.post("/rules/reorder", response_model=list[AllocationRuleResponse])
async def reorder_rules(
    body: RuleReorderRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Renumber allocation rules to match the provided ordered list of IDs."""
    rules = await reorder_allocation_rules(db, body.rule_ids)
    return [AllocationRuleResponse.model_validate(r) for r in rules]
