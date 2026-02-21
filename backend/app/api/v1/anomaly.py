import csv
import io
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.anomaly import (
    AnomalyMarkExpectedRequest,
    AnomalyResponse,
    AnomalySummaryResponse,
    AnomalyStatusUpdate,
)
from app.services.anomaly import (
    get_anomalies,
    get_anomalies_for_export,
    get_anomaly_summary,
    mark_anomaly_expected,
    unmark_anomaly_expected,
    update_anomaly_status,
)

router = APIRouter(tags=["anomalies"])

_VALID_STATUSES = {"new", "investigating", "resolved", "dismissed"}


@router.get("/", response_model=list[AnomalyResponse])
async def list_anomalies(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    service_name: str | None = Query(default=None),
    resource_group: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return all anomalies (full history) with optional filters."""
    rows = await get_anomalies(
        db,
        status=status,
        severity=severity,
        service_name=service_name,
        resource_group=resource_group,
    )
    return [AnomalyResponse.model_validate(row) for row in rows]


@router.get("/summary", response_model=AnomalySummaryResponse)
async def anomaly_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return KPI summary: active counts, potential impact, resolved this month, accuracy."""
    summary_dict = await get_anomaly_summary(db)
    return AnomalySummaryResponse(**summary_dict)


@router.get("/export")
async def export_anomalies(
    severity: str | None = Query(default=None),
    service_name: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Stream a CSV file of anomaly records with optional filters."""
    rows = await get_anomalies_for_export(db, severity=severity, service_name=service_name)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "detected_date",
        "service_name",
        "resource_group",
        "severity",
        "status",
        "pct_deviation",
        "estimated_monthly_impact",
        "description",
    ])
    for row in rows:
        writer.writerow([
            str(row.detected_date),
            row.service_name,
            row.resource_group,
            row.severity,
            row.status,
            float(row.pct_deviation),
            float(row.estimated_monthly_impact),
            row.description,
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=anomaly-report.csv"},
    )


@router.get("/filter-options")
async def filter_options(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Return distinct service_name and resource_group values for filter dropdowns."""
    from sqlalchemy import select, distinct
    from app.models.billing import Anomaly

    services_result = await db.execute(
        select(distinct(Anomaly.service_name)).order_by(Anomaly.service_name)
    )
    services = [r for r in services_result.scalars().all() if r]

    groups_result = await db.execute(
        select(distinct(Anomaly.resource_group)).order_by(Anomaly.resource_group)
    )
    resource_groups = [r for r in groups_result.scalars().all() if r]

    return {"services": services, "resource_groups": resource_groups}


@router.patch("/{anomaly_id}/status", response_model=AnomalyResponse)
async def update_status(
    anomaly_id: uuid.UUID,
    body: AnomalyStatusUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Update an anomaly's status (investigating | resolved | dismissed)."""
    if body.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{body.status}'. Must be one of: {sorted(_VALID_STATUSES)}",
        )
    anomaly = await update_anomaly_status(db, anomaly_id, body.status)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return AnomalyResponse.model_validate(anomaly)


@router.patch("/{anomaly_id}/expected", response_model=AnomalyResponse)
async def mark_expected(
    anomaly_id: uuid.UUID,
    body: AnomalyMarkExpectedRequest = AnomalyMarkExpectedRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Toggle an anomaly's expected flag.

    - expected=True (default): sets expected=True and status='dismissed'
    - expected=False: clears expected=False and resets status='new'
    """
    if body.expected:
        anomaly = await mark_anomaly_expected(db, anomaly_id)
    else:
        anomaly = await unmark_anomaly_expected(db, anomaly_id)
    if anomaly is None:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return AnomalyResponse.model_validate(anomaly)
