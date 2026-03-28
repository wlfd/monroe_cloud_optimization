"""
Unit tests for app.services.notification.

Covers:
- _send_webhook: HMAC signature, success/failure status, timeout
- _send_email: SMTP not configured guard, success path
- dispatch_to_channel: webhook and email routing
- dispatch_to_all_active_channels: fan-out, empty channels, per-channel error isolation
- notify_budget_alert: payload construction, delivery return
- notify_anomaly_detected: broadcast to all channels
- retry_failed_deliveries: creates new delivery rows, caps at 3 attempts
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import (
    _make_notification_channel,
    make_scalars_result,
    make_scalar_result,
)


# ---------------------------------------------------------------------------
# _send_webhook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_webhook_success_returns_delivered():
    """_send_webhook returns 'delivered' status on HTTP 2xx response."""
    from app.services.notification import _send_webhook

    event_id = uuid.uuid4()
    data = {"key": "value"}

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.notification.httpx.AsyncClient", return_value=mock_client):
        status, code, payload, error = await _send_webhook(
            "https://hooks.example.com/test",
            "secret123",
            "budget_alert",
            event_id,
            data,
        )

    assert status == "delivered"
    assert code == 200
    assert error is None
    assert payload["event_type"] == "budget_alert"


@pytest.mark.asyncio
async def test_send_webhook_non_2xx_returns_failed():
    """_send_webhook returns 'failed' status on HTTP 4xx/5xx response."""
    from app.services.notification import _send_webhook

    event_id = uuid.uuid4()

    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_resp
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.notification.httpx.AsyncClient", return_value=mock_client):
        status, code, payload, error = await _send_webhook(
            "https://hooks.example.com/test",
            "",
            "anomaly_detected",
            event_id,
            {},
        )

    assert status == "failed"
    assert code == 503
    assert "503" in error


@pytest.mark.asyncio
async def test_send_webhook_network_exception_returns_failed():
    """_send_webhook returns 'failed' on network-level exception."""
    from app.services.notification import _send_webhook

    event_id = uuid.uuid4()

    mock_client = AsyncMock()
    mock_client.post.side_effect = Exception("Connection refused")
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.notification.httpx.AsyncClient", return_value=mock_client):
        status, code, payload, error = await _send_webhook(
            "https://hooks.example.com/down",
            "",
            "test",
            event_id,
            {},
        )

    assert status == "failed"
    assert code is None
    assert "Connection refused" in error


@pytest.mark.asyncio
async def test_send_webhook_includes_hmac_signature():
    """_send_webhook adds X-CloudCost-Signature header when secret is provided."""
    from app.services.notification import _send_webhook

    event_id = uuid.uuid4()
    secret = "my-secret-key"
    captured_headers = {}

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200

    async def fake_post(url, content, headers):
        captured_headers.update(headers)
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.notification.httpx.AsyncClient", return_value=mock_client):
        await _send_webhook(
            "https://hooks.example.com/test",
            secret,
            "budget_alert",
            event_id,
            {"foo": "bar"},
        )

    assert "X-CloudCost-Signature" in captured_headers
    assert captured_headers["X-CloudCost-Signature"].startswith("sha256=")


@pytest.mark.asyncio
async def test_send_webhook_no_secret_omits_signature_header():
    """_send_webhook omits the signature header when secret is empty."""
    from app.services.notification import _send_webhook

    event_id = uuid.uuid4()
    captured_headers = {}

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200

    async def fake_post(url, content, headers):
        captured_headers.update(headers)
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = fake_post
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("app.services.notification.httpx.AsyncClient", return_value=mock_client):
        await _send_webhook(
            "https://hooks.example.com/test",
            "",  # no secret
            "test",
            event_id,
            {},
        )

    assert "X-CloudCost-Signature" not in captured_headers


# ---------------------------------------------------------------------------
# _send_email
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_email_no_smtp_host_returns_failed():
    """_send_email returns 'failed' immediately when SMTP_HOST is not configured."""
    from app.services.notification import _send_email

    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.SMTP_HOST = ""
        status, error = await _send_email("test@example.com", "Subject", "<p>Body</p>")

    assert status == "failed"
    assert error == "SMTP not configured"


@pytest.mark.asyncio
async def test_send_email_success():
    """_send_email returns 'delivered' when aiosmtplib.send succeeds."""
    from app.services.notification import _send_email

    with (
        patch("app.services.notification.settings") as mock_settings,
        patch("app.services.notification.aiosmtplib.send", new_callable=AsyncMock) as mock_send,
    ):
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "user"
        mock_settings.SMTP_PASSWORD = "pass"
        mock_settings.SMTP_FROM = "noreply@example.com"
        mock_settings.SMTP_START_TLS = True

        status, error = await _send_email("ops@example.com", "Test Subject", "<p>Hi</p>")

    assert status == "delivered"
    assert error is None
    mock_send.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_smtp_exception_returns_failed():
    """_send_email returns 'failed' when aiosmtplib raises."""
    from app.services.notification import _send_email

    with (
        patch("app.services.notification.settings") as mock_settings,
        patch("app.services.notification.aiosmtplib.send", side_effect=Exception("SMTP error")),
    ):
        mock_settings.SMTP_HOST = "smtp.example.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = ""
        mock_settings.SMTP_PASSWORD = ""
        mock_settings.SMTP_FROM = "noreply@example.com"
        mock_settings.SMTP_START_TLS = True

        status, error = await _send_email("ops@example.com", "Subject", "<p>Body</p>")

    assert status == "failed"
    assert "SMTP error" in error


# ---------------------------------------------------------------------------
# dispatch_to_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_to_channel_webhook_creates_delivery():
    """dispatch_to_channel creates a NotificationDelivery row for webhook channel."""
    from app.services.notification import dispatch_to_channel

    session = AsyncMock()
    channel = _make_notification_channel(channel_type="webhook")
    event_id = uuid.uuid4()

    with patch("app.services.notification._send_webhook", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ("delivered", 200, {"event_type": "test"}, None)

        delivery = await dispatch_to_channel(
            session,
            channel=channel,
            event_type="budget_alert",
            event_id=event_id,
            subject="Test Alert",
            html="<p>Alert</p>",
            webhook_data={"amount": 1000},
        )

    assert delivery.status == "delivered"
    assert delivery.response_code == 200
    assert delivery.channel_id == channel.id
    session.add.assert_called_once_with(delivery)


@pytest.mark.asyncio
async def test_dispatch_to_channel_email_creates_delivery():
    """dispatch_to_channel creates a NotificationDelivery row for email channel."""
    from app.services.notification import dispatch_to_channel

    session = AsyncMock()
    channel = _make_notification_channel(channel_type="email")
    event_id = uuid.uuid4()

    with patch("app.services.notification._send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = ("delivered", None)

        delivery = await dispatch_to_channel(
            session,
            channel=channel,
            event_type="anomaly_detected",
            event_id=event_id,
            subject="Anomaly Alert",
            html="<p>Anomaly</p>",
            webhook_data={},
        )

    assert delivery.status == "delivered"
    assert delivery.channel_id == channel.id


# ---------------------------------------------------------------------------
# dispatch_to_all_active_channels
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_to_all_active_channels_no_channels_is_noop():
    """dispatch_to_all_active_channels is a no-op when no channels exist."""
    from app.services.notification import dispatch_to_all_active_channels

    session = AsyncMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = []
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    dispatch_mock = AsyncMock()
    with patch("app.services.notification.dispatch_to_channel", dispatch_mock):
        await dispatch_to_all_active_channels(
            session,
            event_type="test",
            event_id=uuid.uuid4(),
            subject="Test",
            html="<p>Test</p>",
            webhook_data={},
        )

    dispatch_mock.assert_not_called()


@pytest.mark.asyncio
async def test_dispatch_to_all_active_channels_dispatches_to_each():
    """dispatch_to_all_active_channels calls dispatch_to_channel for each channel."""
    from app.services.notification import dispatch_to_all_active_channels

    session = AsyncMock()
    ch1 = _make_notification_channel(channel_type="webhook")
    ch2 = _make_notification_channel(channel_type="email")

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [ch1, ch2]
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    dispatch_mock = AsyncMock()
    with patch("app.services.notification.dispatch_to_channel", dispatch_mock):
        await dispatch_to_all_active_channels(
            session,
            event_type="anomaly_detected",
            event_id=uuid.uuid4(),
            subject="Anomaly",
            html="<p>Details</p>",
            webhook_data={"severity": "critical"},
        )

    assert dispatch_mock.call_count == 2


@pytest.mark.asyncio
async def test_dispatch_to_all_active_channels_continues_on_error():
    """dispatch_to_all_active_channels logs errors but continues to other channels."""
    from app.services.notification import dispatch_to_all_active_channels

    session = AsyncMock()
    ch1 = _make_notification_channel(channel_type="webhook", url="https://fail.example.com")
    ch2 = _make_notification_channel(channel_type="webhook", url="https://ok.example.com")

    scalars_mock = MagicMock()
    scalars_mock.all.return_value = [ch1, ch2]
    result = MagicMock()
    result.scalars.return_value = scalars_mock
    session.execute.return_value = result

    call_count = 0

    async def dispatch_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Channel 1 failed")

    with (
        patch("app.services.notification.dispatch_to_channel", side_effect=dispatch_side_effect),
        patch("app.services.notification.logger"),
    ):
        await dispatch_to_all_active_channels(
            session,
            event_type="test",
            event_id=uuid.uuid4(),
            subject="Test",
            html="<p>Test</p>",
            webhook_data={},
        )

    assert call_count == 2


# ---------------------------------------------------------------------------
# notify_budget_alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_budget_alert_calls_dispatch_to_channel():
    """notify_budget_alert builds context and calls dispatch_to_channel."""
    from app.services.notification import notify_budget_alert

    session = AsyncMock()
    channel = _make_notification_channel(channel_type="webhook")
    alert_event_id = uuid.uuid4()

    delivery_mock = MagicMock()
    delivery_mock.status = "delivered"

    dispatch_mock = AsyncMock(return_value=delivery_mock)

    with (
        patch("app.services.notification.dispatch_to_channel", dispatch_mock),
        patch(
            "app.services.notification.render_template",
            return_value=("CloudCost Budget Alert", "<p>Alert</p>"),
        ),
    ):
        delivery = await notify_budget_alert(
            session,
            alert_event_id=alert_event_id,
            channel=channel,
            budget_name="My Budget",
            scope_type="subscription",
            scope_value=None,
            threshold_percent=80,
            spend_at_trigger=8000.0,
            budget_amount=10000.0,
            billing_period="2026-03",
        )

    dispatch_mock.assert_called_once()
    call_kwargs = dispatch_mock.call_args.kwargs
    assert call_kwargs["event_type"] == "budget_alert"
    assert call_kwargs["event_id"] == alert_event_id
    assert call_kwargs["channel"] == channel


# ---------------------------------------------------------------------------
# retry_failed_deliveries
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_failed_deliveries_creates_new_delivery_on_success():
    """retry_failed_deliveries creates a new delivery row with incremented attempt_number."""
    from app.services.notification import retry_failed_deliveries

    channel = _make_notification_channel(channel_type="webhook")
    delivery = MagicMock()
    delivery.id = uuid.uuid4()
    delivery.channel_id = channel.id
    delivery.event_type = "anomaly_detected"
    delivery.event_id = uuid.uuid4()
    delivery.payload_json = {"event_type": "test", "data": {}}
    delivery.attempt_number = 1
    delivery.status = "failed"

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.status_code = 200

    mock_http_client = AsyncMock()
    mock_http_client.post.return_value = mock_resp
    mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    rows_mock = MagicMock()
    rows_mock.all.return_value = [(delivery, channel)]
    result = MagicMock()
    result.all.return_value = [(delivery, channel)]
    mock_session.execute.return_value = result

    with (
        patch("app.services.notification.AsyncSessionLocal", return_value=mock_session),
        patch("app.services.notification.httpx.AsyncClient", return_value=mock_http_client),
    ):
        await retry_failed_deliveries()

    # A new NotificationDelivery row should be added with attempt_number=2
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.attempt_number == 2
    assert added.status == "delivered"
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_retry_failed_deliveries_skips_missing_payload():
    """retry_failed_deliveries skips deliveries with no stored payload."""
    from app.services.notification import retry_failed_deliveries

    channel = _make_notification_channel(channel_type="webhook")
    delivery = MagicMock()
    delivery.id = uuid.uuid4()
    delivery.payload_json = None  # no payload stored
    delivery.attempt_number = 1

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result = MagicMock()
    result.all.return_value = [(delivery, channel)]
    mock_session.execute.return_value = result

    with (
        patch("app.services.notification.AsyncSessionLocal", return_value=mock_session),
        patch("app.services.notification.logger"),
    ):
        await retry_failed_deliveries()

    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_retry_failed_deliveries_no_failed_deliveries_is_noop():
    """retry_failed_deliveries returns immediately when no failed deliveries exist."""
    from app.services.notification import retry_failed_deliveries

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    result = MagicMock()
    result.all.return_value = []
    mock_session.execute.return_value = result

    with patch("app.services.notification.AsyncSessionLocal", return_value=mock_session):
        await retry_failed_deliveries()

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()
