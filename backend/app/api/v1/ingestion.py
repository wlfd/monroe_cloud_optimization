import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_admin
from app.models.billing import IngestionAlert, IngestionRun
from app.models.user import User
from app.schemas.ingestion import (
    IngestionAlertResponse,
    IngestionRunResponse,
    IngestionStatusResponse,
    TriggerResponse,
)
from app.services.ingestion import is_ingestion_running, run_ingestion

_background_tasks: set = set()

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/run", response_model=TriggerResponse, status_code=202)
async def trigger_manual_run(
    _: User = Depends(require_admin),
):
    """Trigger an immediate ingestion run. Returns 409 if already running."""
    if is_ingestion_running():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ingestion already in progress"
        )
    # Fire-and-forget — do NOT await (long-running background task)
    task = asyncio.create_task(run_ingestion(triggered_by="manual"))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return TriggerResponse(status="accepted")


@router.get("/status", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    _: User = Depends(require_admin),
):
    """Returns whether an ingestion run is currently in progress."""
    return IngestionStatusResponse(running=is_ingestion_running())


@router.get("/runs", response_model=list[IngestionRunResponse])
async def list_ingestion_runs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Returns last N ingestion runs ordered by most recent first."""
    result = await db.execute(
        select(IngestionRun)
        .order_by(desc(IngestionRun.started_at))
        .limit(limit)
    )
    runs = result.scalars().all()
    return [IngestionRunResponse.model_validate(r) for r in runs]


@router.get("/alerts", response_model=list[IngestionAlertResponse])
async def list_ingestion_alerts(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Returns ingestion failure alerts. By default returns only active (uncleared) alerts."""
    query = select(IngestionAlert).order_by(desc(IngestionAlert.created_at))
    if active_only:
        query = query.where(IngestionAlert.is_active == True)  # noqa: E712
    result = await db.execute(query)
    alerts = result.scalars().all()
    return [IngestionAlertResponse.model_validate(a) for a in alerts]
