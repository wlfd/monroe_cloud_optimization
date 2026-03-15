"""Attribution API router.

Provides 4 endpoints under /attribution:
- GET /attribution/          — list monthly attribution totals
- GET /attribution/breakdown/{tenant_id} — per-service breakdown
- GET /attribution/export    — CSV download
- POST /attribution/run      — manual trigger (admin only)

Follows api/v1/anomaly.py style.
"""

import asyncio
import csv
import io
from datetime import date

_background_tasks: set = set()

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db, require_admin
from app.models.user import User
from app.schemas.attribution import ServiceBreakdownItem, TenantAttributionResponse
from app.services.attribution import (
    get_attribution_breakdown,
    get_attributions,
    run_attribution,
)

router = APIRouter(tags=["attribution"])

_today = date.today


@router.get("/", response_model=list[TenantAttributionResponse])
async def list_attributions(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return pre-computed monthly attribution totals for all tenants."""
    today = _today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    rows = await get_attributions(db, year, month)
    return [
        TenantAttributionResponse(
            tenant_id=r.tenant_id,
            display_name=r.display_name,
            year=r.year,
            month=r.month,
            total_cost=r.total_cost,
            pct_of_total=r.pct_of_total,
            mom_delta_usd=r.mom_delta_usd,
            top_service_category=r.top_service_category,
            allocated_cost=r.allocated_cost,
            tagged_cost=r.tagged_cost,
            computed_at=r.computed_at,
        )
        for r in rows
    ]


@router.get("/breakdown/{tenant_id}", response_model=list[ServiceBreakdownItem])
async def attribution_breakdown(
    tenant_id: str,
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return per-service cost breakdown for a single tenant in a given period."""
    today = _today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    rows = await get_attribution_breakdown(db, tenant_id, year, month)
    return [ServiceBreakdownItem(**row) for row in rows]


@router.get("/export")
async def export_attributions(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stream a CSV file of per-tenant attribution data for the given period."""
    today = _today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    rows = await get_attributions(db, year, month)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "tenant_id",
        "display_name",
        "period",
        "total_cost_usd",
        "pct_of_total",
        "mom_delta_usd",
        "top_service_category",
    ])
    for row in rows:
        writer.writerow([
            row.tenant_id,
            row.display_name or "",
            f"{year}-{month:02d}",
            float(row.total_cost),
            float(row.pct_of_total),
            float(row.mom_delta_usd) if row.mom_delta_usd is not None else "",
            row.top_service_category or "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=attribution-{year}-{month:02d}.csv"
        },
    )


async def _run_attribution_task() -> None:
    """Wrapper for fire-and-forget attribution run."""
    try:
        await run_attribution()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Manual attribution run failed: %s", exc)


@router.post("/run", status_code=202)
async def trigger_attribution_run(
    _: User = Depends(require_admin),
):
    """Manually trigger an attribution run (admin only). Returns immediately (202)."""
    task = asyncio.create_task(_run_attribution_task())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"status": "triggered"}
