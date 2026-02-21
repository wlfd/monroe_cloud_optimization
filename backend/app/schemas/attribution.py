"""Pydantic v2 schemas for attribution and settings endpoints.

Follows anomaly.py style: model_config = ConfigDict(from_attributes=True)
on response schemas that map ORM objects.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, model_validator


# ---------------------------------------------------------------------------
# Tenant profile schemas
# ---------------------------------------------------------------------------


class TenantProfileResponse(BaseModel):
    id: uuid.UUID
    tenant_id: str
    display_name: str | None
    is_new: bool
    acknowledged_at: datetime | None
    first_seen: date
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class TenantDisplayNameUpdate(BaseModel):
    display_name: str


# ---------------------------------------------------------------------------
# Allocation rule schemas
# ---------------------------------------------------------------------------


class AllocationRuleResponse(BaseModel):
    id: uuid.UUID
    priority: int
    target_type: str   # 'resource_group' | 'service_category'
    target_value: str
    method: str        # 'by_count' | 'by_usage' | 'manual_pct'
    manual_pct: dict[str, float] | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AllocationRuleCreate(BaseModel):
    target_type: str
    target_value: str
    method: str
    manual_pct: dict[str, float] | None = None

    @model_validator(mode="after")
    def validate_manual_pct(self) -> "AllocationRuleCreate":
        if self.method == "manual_pct":
            if not self.manual_pct:
                raise ValueError("manual_pct is required when method='manual_pct'")
            total = sum(self.manual_pct.values())
            if abs(total - 100.0) > 0.01:
                raise ValueError(f"manual_pct values must sum to 100 (got {total:.2f})")
        return self


class AllocationRuleUpdate(BaseModel):
    target_type: str | None = None
    target_value: str | None = None
    method: str | None = None
    manual_pct: dict[str, float] | None = None


class RuleReorderRequest(BaseModel):
    rule_ids: list[uuid.UUID]  # ordered list; service renumbers 1..N sequentially


# ---------------------------------------------------------------------------
# Attribution response schemas
# ---------------------------------------------------------------------------


class TenantAttributionResponse(BaseModel):
    tenant_id: str
    display_name: str | None
    year: int
    month: int
    total_cost: float
    pct_of_total: float
    mom_delta_usd: float | None
    top_service_category: str | None
    allocated_cost: float
    tagged_cost: float
    computed_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ServiceBreakdownItem(BaseModel):
    service_name: str
    total_cost: float
