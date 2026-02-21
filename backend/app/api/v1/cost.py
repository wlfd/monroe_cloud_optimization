import csv
import io
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.cost import (
    SpendSummaryResponse, DailySpendResponse,
    BreakdownItemResponse, TopResourceResponse,
)
from app.services.cost import (
    get_spend_summary, get_daily_spend,
    get_breakdown, get_top_resources, get_breakdown_for_export,
)

router = APIRouter(prefix="/costs", tags=["costs"])


@router.get("/summary", response_model=SpendSummaryResponse)
async def spend_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return MTD spend, end-of-month projection, prior month total, and MoM delta."""
    data = await get_spend_summary(db)
    return SpendSummaryResponse(**data)


@router.get("/trend", response_model=list[DailySpendResponse])
async def spend_trend(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return daily spend totals for the past N days (1-90)."""
    rows = await get_daily_spend(db, days=days)
    return [
        DailySpendResponse(usage_date=str(r.usage_date), total_cost=float(r.total_cost))
        for r in rows
    ]


@router.get("/breakdown", response_model=list[BreakdownItemResponse])
async def spend_breakdown(
    dimension: str = Query(
        default="service_name",
        pattern="^(service_name|resource_group|region|tag)$",
    ),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return spend grouped by the specified dimension for the past N days."""
    try:
        rows = await get_breakdown(db, dimension=dimension, days=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [
        BreakdownItemResponse(
            dimension_value=str(r.dimension_value or ""),
            total_cost=float(r.total_cost),
        )
        for r in rows
        if r.dimension_value  # filter out blank dimension values (unlabeled rows)
    ]


@router.get("/top-resources", response_model=list[TopResourceResponse])
async def top_resources(
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return top 10 resources by total cost for the past N days."""
    rows = await get_top_resources(db, days=days)
    return [
        TopResourceResponse(
            resource_id=r.resource_id,
            resource_name=r.resource_name,
            service_name=r.service_name,
            resource_group=r.resource_group,
            total_cost=float(r.total_cost),
        )
        for r in rows
    ]


@router.get("/export")
async def export_costs(
    dimension: str = Query(
        default="service_name",
        pattern="^(service_name|resource_group|region|tag)$",
    ),
    days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stream a CSV file of spend breakdown by the specified dimension."""
    rows = await get_breakdown_for_export(db, dimension=dimension, days=days)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["dimension", "total_cost_usd"])
    for row in rows:
        writer.writerow([str(row.dimension_value or ""), float(row.total_cost)])
    output.seek(0)  # reset buffer AFTER writing, BEFORE streaming
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cost-breakdown.csv"},
    )
