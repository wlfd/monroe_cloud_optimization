from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    id: UUID
    detected_date: date
    service_name: str
    resource_group: str
    description: str
    severity: str
    status: str
    expected: bool
    pct_deviation: float
    estimated_monthly_impact: float
    baseline_daily_avg: float
    current_daily_cost: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnomalySummaryResponse(BaseModel):
    active_count: int
    critical_count: int
    high_count: int
    medium_count: int
    total_potential_impact: float
    resolved_this_month: int
    detection_accuracy: Optional[float] = None


class AnomalyStatusUpdate(BaseModel):
    status: str  # 'investigating' | 'resolved' | 'dismissed'


class AnomalyMarkExpectedRequest(BaseModel):
    expected: bool = True
