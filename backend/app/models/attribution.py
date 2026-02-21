"""Attribution SQLAlchemy models.

Stores tenant profiles, allocation rules, and pre-computed monthly attribution totals.
Supports Phase 6 multi-tenant cost attribution.

Follows billing.py pattern: utcnow() defined locally, UUID PK,
Mapped[] typed columns, __table_args__ for indexes and constraints.
"""
import uuid
from datetime import datetime, date, timezone
from decimal import Decimal

from sqlalchemy import String, Boolean, Integer, Numeric, DateTime, Date, JSON, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TenantProfile(Base):
    """Tracks distinct tenant_id tag values with display metadata.

    tenant_id corresponds to raw BillingRecord.tag values.
    is_new drives the "New" badge in the UI until acknowledged.
    """

    __tablename__ = "tenant_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)


class AllocationRule(Base):
    """Defines how shared resource costs are split across tenants.

    method values:
    - 'by_count': split equally among matched tenants
    - 'by_usage': split proportionally by tenant usage
    - 'manual_pct': split by explicit percentages in manual_pct JSON field

    priority ordering: lower number = evaluated first (first-rule-wins).
    """

    __tablename__ = "allocation_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)   # 'resource_group' | 'service_category'
    target_value: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "rg-shared" or "Compute"
    method: Mapped[str] = mapped_column(String(50), nullable=False)         # 'by_count' | 'by_usage' | 'manual_pct'
    manual_pct: Mapped[dict | None] = mapped_column(JSON, nullable=True)    # {tenant_id: pct}, only for method='manual_pct'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("priority", name="uq_allocation_rule_priority"),
    )


class TenantAttribution(Base):
    """Pre-computed monthly cost totals per tenant.

    tenant_id may be 'UNALLOCATED' sentinel for costs that matched no allocation rule
    and carry no tenant tag. 'UNALLOCATED' never corresponds to a TenantProfile row.

    Unique constraint on (tenant_id, year, month) enforces one row per tenant per period.
    Indexes on (year, month) and tenant_id support dashboard queries.
    """

    __tablename__ = "tenant_attributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    pct_of_total: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False, default=0)
    mom_delta_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)   # None if no prior month data
    top_service_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    allocated_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    tagged_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "year", "month", name="uq_tenant_attribution_key"),
        Index("idx_attribution_year_month", "year", "month"),
        Index("idx_attribution_tenant_id", "tenant_id"),
    )
