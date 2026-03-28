"""Recommendation SQLAlchemy model.

Stores LLM-generated cost optimization recommendations.
Uses generated_date for daily-replace semantics: the service layer
always queries WHERE generated_date = MAX(generated_date).

Follows billing.py pattern: utcnow() defined locally, UUID PK,
Mapped[] typed columns, __table_args__ for indexes.
"""
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    generated_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Resource identity (matches billing_records columns for join)
    resource_name: Mapped[str] = mapped_column(String(500), nullable=False)
    resource_group: Mapped[str] = mapped_column(String(255), nullable=False)
    subscription_id: Mapped[str] = mapped_column(String(255), nullable=False)
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    meter_category: Mapped[str] = mapped_column(String(255), nullable=False)

    # LLM output fields (AI-02)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # right-sizing | idle | reserved | storage
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    estimated_monthly_savings: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Stored at generation time from billing_records (30-day average) for UI comparison panel
    current_monthly_cost: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (
        Index("idx_recommendation_generated_date", "generated_date"),
        Index("idx_recommendation_category", "category"),
        Index("idx_recommendation_resource", "resource_name", "resource_group"),
    )
