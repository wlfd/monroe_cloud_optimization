from pydantic import BaseModel
from typing import Optional


class SpendSummaryResponse(BaseModel):
    mtd_total: float
    projected_month_end: float
    prior_month_total: float
    mom_delta_pct: Optional[float]  # null when prior month has zero spend (first period)


class DailySpendResponse(BaseModel):
    usage_date: str   # ISO date string, e.g. "2026-01-15"
    total_cost: float


class BreakdownItemResponse(BaseModel):
    dimension_value: str
    total_cost: float


class TopResourceResponse(BaseModel):
    resource_id: str
    resource_name: str
    service_name: str
    resource_group: str
    total_cost: float
