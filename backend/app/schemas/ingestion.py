from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class IngestionRunResponse(BaseModel):
    id: UUID
    started_at: datetime
    completed_at: datetime | None
    status: str                   # 'running' | 'success' | 'failed' | 'interrupted'
    triggered_by: str             # 'scheduler' | 'manual' | 'backfill'
    records_ingested: int
    window_start: datetime | None
    window_end: datetime | None
    retry_count: int
    error_detail: str | None

    model_config = {"from_attributes": True}


class IngestionAlertResponse(BaseModel):
    id: UUID
    created_at: datetime
    error_message: str
    retry_count: int
    failed_at: datetime
    is_active: bool
    cleared_at: datetime | None
    cleared_by: str | None

    model_config = {"from_attributes": True}


class IngestionStatusResponse(BaseModel):
    running: bool


class TriggerResponse(BaseModel):
    status: str   # "accepted"
