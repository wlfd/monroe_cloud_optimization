"""Notification delivery service.

Handles email (SMTP via aiosmtplib) and webhook (HTTP POST with HMAC-SHA256
signing via httpx) delivery for budget alerts, anomaly detections, and
ingestion failures.

All dispatch functions accept an AsyncSession and add NotificationDelivery rows
but do NOT commit — the caller is responsible for committing.

The one exception is retry_failed_deliveries(), which manages its own session
as it is called from the scheduler outside request context.
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import aiosmtplib
import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.notification import NotificationChannel, NotificationDelivery

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "email"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


def render_template(template_name: str, context: dict) -> tuple[str, str]:
    """Render a Jinja2 HTML email template.

    Returns (subject, html_body). The subject is passed in context["subject"].
    """
    tmpl = _jinja_env.get_template(template_name)
    html = tmpl.render(**context)
    return context.get("subject", "CloudCost Alert"), html


# ---------------------------------------------------------------------------
# Low-level send helpers
# ---------------------------------------------------------------------------


async def _send_email(to_address: str, subject: str, html_body: str) -> tuple[str, str | None]:
    """Send an HTML email via SMTP. Returns (status, error_message)."""
    if not settings.SMTP_HOST:
        logger.warning("_send_email: SMTP_HOST not configured — skipping email")
        return "failed", "SMTP not configured"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_address
    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=settings.SMTP_START_TLS,
        )
        return "delivered", None
    except Exception as exc:
        logger.error("_send_email: failed to %s: %s", to_address, exc)
        return "failed", str(exc)


async def _send_webhook(
    url: str,
    secret: str,
    event_type: str,
    event_id: uuid.UUID,
    data: dict,
) -> tuple[str, int | None, dict, str | None]:
    """Send a signed HTTP POST webhook. Returns (status, response_code, payload, error_message).

    The returned payload dict is stored in notification_deliveries for retries.
    """
    payload = {
        "event_type": event_type,
        "event_id": str(event_id),
        "timestamp": datetime.now(UTC).isoformat(),
        "data": data,
    }
    body = json.dumps(payload, default=str)

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if secret:
        sig = hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()
        headers["X-CloudCost-Signature"] = f"sha256={sig}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, content=body, headers=headers)
        if resp.is_success:
            return "delivered", resp.status_code, payload, None
        error = f"HTTP {resp.status_code}: {resp.text[:200]}"
        return "failed", resp.status_code, payload, error
    except Exception as exc:
        logger.error("_send_webhook: failed to %s: %s", url, exc)
        return "failed", None, payload, str(exc)


# ---------------------------------------------------------------------------
# Core dispatch to a single channel
# ---------------------------------------------------------------------------


async def dispatch_to_channel(
    session: AsyncSession,
    *,
    channel: NotificationChannel,
    event_type: str,
    event_id: uuid.UUID,
    subject: str,
    html: str,
    webhook_data: dict,
    attempt_number: int = 1,
) -> NotificationDelivery:
    """Deliver an alert to a single channel and log the attempt.

    Returns the NotificationDelivery row (not yet committed).
    """
    status: str
    response_code: int | None = None
    error_message: str | None = None
    payload_json: dict | None = None

    if channel.channel_type == "email":
        to_address = channel.config_json.get("address", "")
        status, error_message = await _send_email(to_address, subject, html)

    else:  # webhook
        url = channel.config_json.get("url", "")
        secret = channel.config_json.get("secret", "")
        status, response_code, payload_json, error_message = await _send_webhook(
            url, secret, event_type, event_id, webhook_data
        )

    delivery = NotificationDelivery(
        channel_id=channel.id,
        event_type=event_type,
        event_id=event_id,
        payload_json=payload_json,
        attempt_number=attempt_number,
        status=status,
        response_code=response_code,
        error_message=error_message,
    )
    session.add(delivery)
    return delivery


# ---------------------------------------------------------------------------
# Dispatch to all active channels (anomaly and ingestion failure events)
# ---------------------------------------------------------------------------


async def dispatch_to_all_active_channels(
    session: AsyncSession,
    *,
    event_type: str,
    event_id: uuid.UUID,
    subject: str,
    html: str,
    webhook_data: dict,
) -> None:
    """Deliver an alert to every active notification channel.

    Used for anomaly_detected and ingestion_failed events where there is no
    specific channel assignment. Errors on individual channels are logged but
    do not stop delivery to remaining channels.

    Caller is responsible for committing the session after this returns.
    """
    stmt = select(NotificationChannel).where(NotificationChannel.is_active == True)  # noqa: E712
    channels = (await session.execute(stmt)).scalars().all()

    if not channels:
        logger.info("dispatch_to_all_active_channels: no active channels configured")
        return

    for channel in channels:
        try:
            await dispatch_to_channel(
                session,
                channel=channel,
                event_type=event_type,
                event_id=event_id,
                subject=subject,
                html=html,
                webhook_data=webhook_data,
            )
        except Exception as exc:
            logger.error(
                "dispatch_to_all_active_channels: channel %s (%s) raised: %s",
                channel.id,
                channel.channel_type,
                exc,
            )


# ---------------------------------------------------------------------------
# Convenience builders for each event type
# ---------------------------------------------------------------------------


async def notify_budget_alert(
    session: AsyncSession,
    *,
    alert_event_id: uuid.UUID,
    channel: NotificationChannel,
    budget_name: str,
    scope_type: str,
    scope_value: str | None,
    threshold_percent: int,
    spend_at_trigger: float,
    budget_amount: float,
    billing_period: str,
) -> NotificationDelivery:
    """Send a budget threshold alert to one specific channel."""
    context = {
        "subject": f"CloudCost Budget Alert: {budget_name} reached {threshold_percent}%",
        "budget_name": budget_name,
        "scope_type": scope_type,
        "scope_value": scope_value or "All",
        "threshold_percent": threshold_percent,
        "spend_at_trigger": spend_at_trigger,
        "budget_amount": budget_amount,
        "billing_period": billing_period,
        "spend_percent": round(spend_at_trigger / budget_amount * 100, 1) if budget_amount else 0,
    }
    subject, html = render_template("budget_alert.html", context)
    webhook_data = {
        "budget_name": budget_name,
        "scope_type": scope_type,
        "scope_value": scope_value,
        "threshold_percent": threshold_percent,
        "spend_at_trigger": spend_at_trigger,
        "budget_amount": budget_amount,
        "billing_period": billing_period,
    }
    return await dispatch_to_channel(
        session,
        channel=channel,
        event_type="budget_alert",
        event_id=alert_event_id,
        subject=subject,
        html=html,
        webhook_data=webhook_data,
    )


async def notify_anomaly_detected(
    session: AsyncSession,
    *,
    anomaly_id: uuid.UUID,
    service_name: str,
    resource_group: str,
    severity: str,
    pct_deviation: float,
    estimated_monthly_impact: float,
    baseline_daily_avg: float,
    current_daily_cost: float,
    detected_date: str,
) -> None:
    """Broadcast a new anomaly detection to all active channels."""
    context = {
        "subject": f"CloudCost Anomaly [{severity.upper()}]: {service_name} / {resource_group}",
        "service_name": service_name,
        "resource_group": resource_group,
        "severity": severity,
        "pct_deviation": round(pct_deviation, 1),
        "estimated_monthly_impact": estimated_monthly_impact,
        "baseline_daily_avg": baseline_daily_avg,
        "current_daily_cost": current_daily_cost,
        "detected_date": detected_date,
    }
    subject, html = render_template("anomaly_detected.html", context)
    webhook_data = {
        "service_name": service_name,
        "resource_group": resource_group,
        "severity": severity,
        "pct_deviation": pct_deviation,
        "estimated_monthly_impact": estimated_monthly_impact,
        "detected_date": detected_date,
    }
    await dispatch_to_all_active_channels(
        session,
        event_type="anomaly_detected",
        event_id=anomaly_id,
        subject=subject,
        html=html,
        webhook_data=webhook_data,
    )


async def notify_ingestion_failed(
    session: AsyncSession,
    *,
    ingestion_alert_id: uuid.UUID,
    error_message: str,
    retry_count: int,
) -> None:
    """Broadcast an ingestion pipeline failure to all active channels."""
    context = {
        "subject": "CloudCost Alert: Data ingestion pipeline failed",
        "error_message": error_message,
        "retry_count": retry_count,
    }
    subject, html = render_template("ingestion_failed.html", context)
    webhook_data = {
        "error_message": error_message,
        "retry_count": retry_count,
    }
    await dispatch_to_all_active_channels(
        session,
        event_type="ingestion_failed",
        event_id=ingestion_alert_id,
        subject=subject,
        html=html,
        webhook_data=webhook_data,
    )


# ---------------------------------------------------------------------------
# Scheduled retry job for failed webhook deliveries
# ---------------------------------------------------------------------------


async def retry_failed_deliveries() -> None:
    """Retry webhook deliveries that failed, up to 3 total attempts.

    Called by the scheduler every 15 minutes. Opens its own session.
    Only retries webhook channels (email retries are not supported).
    """
    async with AsyncSessionLocal() as session:
        stmt = (
            select(NotificationDelivery, NotificationChannel)
            .join(NotificationChannel, NotificationDelivery.channel_id == NotificationChannel.id)
            .where(
                NotificationDelivery.status == "failed",
                NotificationDelivery.attempt_number < 3,
                NotificationChannel.channel_type == "webhook",
                NotificationChannel.is_active == True,  # noqa: E712
            )
            .order_by(NotificationDelivery.attempted_at)
        )
        rows = (await session.execute(stmt)).all()

        if not rows:
            return

        logger.info("retry_failed_deliveries: retrying %d failed webhook(s)", len(rows))

        for delivery, channel in rows:
            if not delivery.payload_json:
                logger.warning(
                    "retry_failed_deliveries: delivery %s has no stored payload — skipping",
                    delivery.id,
                )
                continue

            url = channel.config_json.get("url", "")
            secret = channel.config_json.get("secret", "")
            body = json.dumps(delivery.payload_json, default=str)

            headers: dict[str, str] = {"Content-Type": "application/json"}
            if secret:
                sig = hmac.new(
                    secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256
                ).hexdigest()
                headers["X-CloudCost-Signature"] = f"sha256={sig}"

            new_status: str
            new_code: int | None = None
            new_error: str | None = None

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, content=body, headers=headers)
                if resp.is_success:
                    new_status = "delivered"
                    new_code = resp.status_code
                else:
                    new_status = "failed"
                    new_code = resp.status_code
                    new_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
            except Exception as exc:
                new_status = "failed"
                new_error = str(exc)

            retry = NotificationDelivery(
                channel_id=channel.id,
                event_type=delivery.event_type,
                event_id=delivery.event_id,
                payload_json=delivery.payload_json,
                attempt_number=delivery.attempt_number + 1,
                status=new_status,
                response_code=new_code,
                error_message=new_error,
            )
            session.add(retry)

        await session.commit()
        logger.info("retry_failed_deliveries: done")
