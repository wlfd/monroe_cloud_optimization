"""Budget management API.

Endpoints:
  GET    /budgets                          — list active budgets with current spend
  POST   /budgets                          — create budget (admin / finance)
  GET    /budgets/{id}                     — budget detail + thresholds + spend
  PUT    /budgets/{id}                     — update name / amount / end_date (admin / finance)
  DELETE /budgets/{id}                     — soft-delete (admin)
  POST   /budgets/{id}/thresholds          — add threshold (admin / finance)
  DELETE /budgets/{id}/thresholds/{tid}    — remove threshold (admin)
  GET    /budgets/{id}/alerts              — alert event history
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.budget import (
    AlertEventResponse,
    BudgetCreate,
    BudgetResponse,
    BudgetThresholdCreate,
    BudgetThresholdResponse,
    BudgetUpdate,
    BudgetWithSpendResponse,
)
from app.services.budget import (
    add_threshold,
    create_budget,
    deactivate_budget,
    get_alert_events,
    get_budget,
    get_budgets,
    get_current_period_spend,
    get_thresholds,
    remove_threshold,
    update_budget,
)

router = APIRouter(tags=["budgets"])

_FINANCE_AND_ABOVE = {"admin", "finance"}


def _require_finance_or_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in _FINANCE_AND_ABOVE:
        raise HTTPException(status_code=403, detail="Finance or admin role required")
    return current_user


@router.get("/", response_model=list[BudgetWithSpendResponse])
async def list_budgets(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all active budgets enriched with current-period spend."""
    budgets = await get_budgets(db)
    results = []
    for b in budgets:
        spend = float(await get_current_period_spend(db, b))
        pct = round(spend / float(b.amount_usd) * 100, 1) if b.amount_usd else 0.0
        results.append(
            BudgetWithSpendResponse(
                **BudgetResponse.model_validate(b).model_dump(),
                current_spend_usd=spend,
                spend_percent=pct,
            )
        )
    return results


@router.post("/", response_model=BudgetResponse, status_code=201)
async def create_budget_endpoint(
    body: BudgetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_finance_or_admin),
):
    """Create a new budget. Finance and Admin roles only."""
    budget = await create_budget(
        db,
        name=body.name,
        scope_type=body.scope_type,
        scope_value=body.scope_value,
        amount_usd=body.amount_usd,
        period=body.period,
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=current_user.id,
    )
    return BudgetResponse.model_validate(budget)


@router.get("/{budget_id}", response_model=BudgetWithSpendResponse)
async def get_budget_detail(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Budget detail with current-period spend."""
    budget = await get_budget(db, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    spend = float(await get_current_period_spend(db, budget))
    pct = round(spend / float(budget.amount_usd) * 100, 1) if budget.amount_usd else 0.0
    return BudgetWithSpendResponse(
        **BudgetResponse.model_validate(budget).model_dump(),
        current_spend_usd=spend,
        spend_percent=pct,
    )


@router.put("/{budget_id}", response_model=BudgetResponse)
async def update_budget_endpoint(
    budget_id: uuid.UUID,
    body: BudgetUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_finance_or_admin),
):
    """Update budget name, amount, or end date. Finance and Admin roles only."""
    budget = await update_budget(
        db,
        budget_id,
        name=body.name,
        amount_usd=body.amount_usd,
        end_date=body.end_date,
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}", status_code=204)
async def delete_budget_endpoint(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Soft-delete a budget (sets is_active=False). Admin only."""
    budget = await deactivate_budget(db, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")


@router.post("/{budget_id}/thresholds", response_model=BudgetThresholdResponse, status_code=201)
async def add_budget_threshold(
    budget_id: uuid.UUID,
    body: BudgetThresholdCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_require_finance_or_admin),
):
    """Add an alert threshold to a budget. Finance and Admin roles only."""
    threshold = await add_threshold(
        db,
        budget_id,
        threshold_percent=body.threshold_percent,
        notification_channel_id=body.notification_channel_id,
    )
    if threshold is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    return BudgetThresholdResponse.model_validate(threshold)


@router.get("/{budget_id}/thresholds", response_model=list[BudgetThresholdResponse])
async def list_budget_thresholds(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all thresholds for a budget, ordered by percentage ascending."""
    budget = await get_budget(db, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    thresholds = await get_thresholds(db, budget_id)
    return [BudgetThresholdResponse.model_validate(t) for t in thresholds]


@router.delete("/{budget_id}/thresholds/{threshold_id}", status_code=204)
async def remove_budget_threshold(
    budget_id: uuid.UUID,
    threshold_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Remove a threshold from a budget. Admin only."""
    deleted = await remove_threshold(db, threshold_id, budget_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Threshold not found")


@router.get("/{budget_id}/alerts", response_model=list[AlertEventResponse])
async def list_alert_events(
    budget_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Alert event history for a budget, most recent first."""
    budget = await get_budget(db, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    events = await get_alert_events(db, budget_id)
    return [AlertEventResponse.model_validate(e) for e in events]
