"""add_budget_and_notification_tables

Revision ID: c8f1a9b3d2e4
Revises: 29e392128bad
Create Date: 2026-03-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c8f1a9b3d2e4"
down_revision: Union[str, Sequence[str], None] = "29e392128bad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- notification_channels (must come before budget_thresholds FK) ------
    op.create_table(
        "notification_channels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("channel_type", sa.String(length=20), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_notification_channels_active", "notification_channels", ["is_active"])

    # --- notification_deliveries ---------------------------------------------
    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("channel_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["notification_channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_notification_deliveries_event",
        "notification_deliveries",
        ["event_type", "event_id"],
    )
    op.create_index(
        "idx_notification_deliveries_failed",
        "notification_deliveries",
        ["status", "attempt_number"],
    )

    # --- budgets -------------------------------------------------------------
    op.create_table(
        "budgets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("scope_type", sa.String(length=50), nullable=False),
        sa.Column("scope_value", sa.String(length=500), nullable=True),
        sa.Column("amount_usd", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("period", sa.String(length=20), nullable=False, server_default="monthly"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_budgets_active", "budgets", ["is_active"])

    # --- budget_thresholds ---------------------------------------------------
    op.create_table(
        "budget_thresholds",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("notification_channel_id", sa.UUID(), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_triggered_period", sa.String(length=7), nullable=True),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["notification_channel_id"], ["notification_channels.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_budget_thresholds_budget_id", "budget_thresholds", ["budget_id"])

    # --- alert_events --------------------------------------------------------
    op.create_table(
        "alert_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("budget_id", sa.UUID(), nullable=False),
        sa.Column("threshold_id", sa.UUID(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("billing_period", sa.String(length=7), nullable=False),
        sa.Column("spend_at_trigger", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("budget_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("threshold_percent", sa.Integer(), nullable=False),
        sa.Column("delivery_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["budget_id"], ["budgets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["threshold_id"], ["budget_thresholds.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_alert_events_budget_id", "alert_events", ["budget_id"])
    op.create_index("idx_alert_events_triggered_at", "alert_events", ["triggered_at"])


def downgrade() -> None:
    op.drop_index("idx_alert_events_triggered_at", table_name="alert_events")
    op.drop_index("idx_alert_events_budget_id", table_name="alert_events")
    op.drop_table("alert_events")

    op.drop_index("idx_budget_thresholds_budget_id", table_name="budget_thresholds")
    op.drop_table("budget_thresholds")

    op.drop_index("idx_budgets_active", table_name="budgets")
    op.drop_table("budgets")

    op.drop_index("idx_notification_deliveries_failed", table_name="notification_deliveries")
    op.drop_index("idx_notification_deliveries_event", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")

    op.drop_index("idx_notification_channels_active", table_name="notification_channels")
    op.drop_table("notification_channels")
