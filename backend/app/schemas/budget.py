from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

_VALID_SCOPE_TYPES = {"subscription", "resource_group", "service", "tag"}
_VALID_PERIODS = {"monthly", "annual"}


class BudgetCreate(BaseModel):
    name: str
    scope_type: str
    scope_value: str | None = None
    amount_usd: Decimal
    period: str = "monthly"
    start_date: date
    end_date: date | None = None

    @field_validator("scope_type")
    @classmethod
    def validate_scope_type(cls, v: str) -> str:
        if v not in _VALID_SCOPE_TYPES:
            raise ValueError(f"scope_type must be one of: {sorted(_VALID_SCOPE_TYPES)}")
        return v

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        if v not in _VALID_PERIODS:
            raise ValueError(f"period must be one of: {sorted(_VALID_PERIODS)}")
        return v

    @field_validator("amount_usd")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount_usd must be greater than 0")
        return v


class BudgetUpdate(BaseModel):
    name: str | None = None
    amount_usd: Decimal | None = None
    end_date: date | None = None

    @field_validator("amount_usd")
    @classmethod
    def validate_amount(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("amount_usd must be greater than 0")
        return v


class BudgetResponse(BaseModel):
    id: UUID
    name: str
    scope_type: str
    scope_value: str | None
    amount_usd: float
    period: str
    start_date: date
    end_date: date | None
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BudgetWithSpendResponse(BudgetResponse):
    """Budget response enriched with current-period spend and utilization."""

    current_spend_usd: float
    spend_percent: float


class BudgetThresholdCreate(BaseModel):
    threshold_percent: int
    notification_channel_id: UUID | None = None

    @field_validator("threshold_percent")
    @classmethod
    def validate_percent(cls, v: int) -> int:
        if not (1 <= v <= 200):
            raise ValueError("threshold_percent must be between 1 and 200")
        return v


class BudgetThresholdResponse(BaseModel):
    id: UUID
    budget_id: UUID
    threshold_percent: int
    notification_channel_id: UUID | None
    last_triggered_at: datetime | None
    last_triggered_period: str | None

    model_config = {"from_attributes": True}


class AlertEventResponse(BaseModel):
    id: UUID
    budget_id: UUID
    threshold_id: UUID | None
    triggered_at: datetime
    billing_period: str
    spend_at_trigger: float
    budget_amount: float
    threshold_percent: int
    delivery_status: str

    model_config = {"from_attributes": True}
