import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow


class NotificationChannel(Base):
    """Email or webhook endpoint that receives alerts."""

    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # channel_type: 'email' | 'webhook'
    # email config:   {"address": "ops@example.com"}
    # webhook config: {"url": "https://...", "secret": "hmac_secret"}
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    __table_args__ = (Index("idx_notification_channels_active", "is_active"),)


class NotificationDelivery(Base):
    """Log of every delivery attempt for any alert event."""

    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("notification_channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # event_type: 'budget_alert' | 'anomaly_detected' | 'ingestion_failed'
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Generic reference to the triggering entity — no FK since sources differ
    payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Stored for webhook retries; null for email deliveries
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # status: 'delivered' | 'failed' | 'pending'
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_notification_deliveries_event", "event_type", "event_id"),
        Index("idx_notification_deliveries_failed", "status", "attempt_number"),
    )
