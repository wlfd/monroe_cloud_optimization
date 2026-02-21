"""Pydantic response schemas for recommendations."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel


class RecommendationOut(BaseModel):
    id: uuid.UUID
    generated_date: date
    resource_name: str
    resource_group: str
    subscription_id: str
    service_name: str
    meter_category: str
    category: str
    explanation: str
    estimated_monthly_savings: float
    confidence_score: int
    current_monthly_cost: float
    created_at: datetime

    model_config = {"from_attributes": True}


class RecommendationSummary(BaseModel):
    total_count: int
    potential_monthly_savings: float
    by_category: dict[str, int]
    daily_limit_reached: bool
    calls_used_today: int
    daily_call_limit: int
