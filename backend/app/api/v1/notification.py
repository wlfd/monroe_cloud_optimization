"""Notification channel admin API.

Endpoints (admin only):
  GET    /notifications/channels          — list all channels
  POST   /notifications/channels          — create email or webhook channel
  DELETE /notifications/channels/{id}     — delete a channel
  GET    /notifications/channels/{id}/deliveries — delivery history for a channel
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_admin
from app.models.notification import NotificationChannel, NotificationDelivery
from app.models.user import User
from app.schemas.notification import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationDeliveryResponse,
)

router = APIRouter(tags=["notifications"])


@router.get("/channels", response_model=list[NotificationChannelResponse])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List all notification channels. Admin only."""
    stmt = select(NotificationChannel).order_by(NotificationChannel.created_at.desc())
    channels = (await db.execute(stmt)).scalars().all()
    return [NotificationChannelResponse.model_validate(c) for c in channels]


@router.post("/channels", response_model=NotificationChannelResponse, status_code=201)
async def create_channel(
    body: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create an email or webhook notification channel. Admin only."""
    channel = NotificationChannel(
        name=body.name,
        channel_type=body.channel_type,
        config_json=body.config_json,
        owner_user_id=current_user.id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return NotificationChannelResponse.model_validate(channel)


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Delete a notification channel. Admin only.

    Note: budget thresholds referencing this channel will have their
    notification_channel_id set to NULL (ON DELETE SET NULL).
    """
    stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    channel = (await db.execute(stmt)).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(channel)
    await db.commit()


@router.get("/channels/{channel_id}/deliveries", response_model=list[NotificationDeliveryResponse])
async def list_deliveries(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Delivery attempt history for a specific channel. Admin only."""
    channel_stmt = select(NotificationChannel).where(NotificationChannel.id == channel_id)
    channel = (await db.execute(channel_stmt)).scalar_one_or_none()
    if channel is None:
        raise HTTPException(status_code=404, detail="Channel not found")

    stmt = (
        select(NotificationDelivery)
        .where(NotificationDelivery.channel_id == channel_id)
        .order_by(NotificationDelivery.attempted_at.desc())
        .limit(100)
    )
    deliveries = (await db.execute(stmt)).scalars().all()
    return [NotificationDeliveryResponse.model_validate(d) for d in deliveries]
