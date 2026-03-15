import uuid
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, DateTime, Date, Numeric, Integer, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base, utcnow


class Budget(Base):
    """A spending limit scoped to a subscription, resource group, service, or tag."""

    __tablename__ = "budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # scope_type: 'subscription' | 'resource_group' | 'service' | 'tag'
    scope_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # scope_value: NULL for subscription scope; otherwise the RG name, service name, or tag value
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    # period: 'monthly' | 'annual'
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    __table_args__ = (Index("idx_budgets_active", "is_active"),)


class BudgetThreshold(Base):
    """A percentage threshold on a budget that triggers an alert when crossed."""

    __tablename__ = "budget_thresholds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False
    )
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    # Supports 1–200 to allow tracking over-budget spend (e.g. 150% = 50% over budget)
    notification_channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_period: Mapped[str | None] = mapped_column(String(7), nullable=True)
    # last_triggered_period: 'YYYY-MM' for monthly, 'YYYY' for annual
    # Used to prevent re-firing in the same billing period

    __table_args__ = (Index("idx_budget_thresholds_budget_id", "budget_id"),)


class AlertEvent(Base):
    """A record of a budget threshold being crossed."""

    __tablename__ = "alert_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    budget_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False
    )
    threshold_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("budget_thresholds.id", ondelete="SET NULL"), nullable=True
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False)
    # billing_period: 'YYYY-MM' for monthly, 'YYYY' for annual
    spend_at_trigger: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    budget_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # delivery_status: 'pending' | 'delivered' | 'failed' | 'no_channel'

    __table_args__ = (
        Index("idx_alert_events_budget_id", "budget_id"),
        Index("idx_alert_events_triggered_at", "triggered_at"),
    )
