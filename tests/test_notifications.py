import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from unittest.mock import MagicMock, patch
import pytest
import httpx

from app.models.db.notification_recipient import NotificationRecipient
from app.services.notification.slack import SlackNotificationChannel
from app.services.notification.smtp import SmtpNotificationChannel
from app.services.notification.registry import NOTIFICATION_CHANNELS
from workers.notification.processor import process_notification

@patch("app.services.notification.smtp.smtplib.SMTP")
def test_smtp_notification_channel_db_lookup(mock_smtp_cls):
    mock_db = MagicMock()
    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    mock_db.execute.return_value.scalars.return_value.all.return_value = [
        "admin1@example.com",
        "admin2@example.com"
    ]

    with patch("app.services.notification.smtp.settings") as mock_settings:
        mock_settings.SMTP_HOST = "smtp.mail.com"
        mock_settings.SMTP_PORT = 587
        mock_settings.SMTP_USER = "test"
        mock_settings.SMTP_PASSWORD = "pwd"
        mock_settings.NOTIFICATION_EMAIL_SENDER = "no-reply@test.com"

        channel = SmtpNotificationChannel()
        channel.send_message(
            subject="Test Alert",
            message="This is a test notification payload.",
            db=mock_db,
            details={"topic": "job-failed"}
        )

        mock_db.execute.assert_called_once()
        mock_smtp_cls.assert_called_once_with("smtp.mail.com", 587, timeout=15)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test", "pwd")
        mock_server.sendmail.assert_called_once()

def test_slack_notifier_stub_no_crash():
    mock_db = MagicMock()
    channel = SlackNotificationChannel()
    
    with patch("app.services.notification.slack.settings") as mock_slack_settings:
        mock_slack_settings.SLACK_WEBHOOK_URL = None
        channel.send_message("Slack test", "Hello Slack!", mock_db)
    
    assert len(NOTIFICATION_CHANNELS) == 2
    assert isinstance(NOTIFICATION_CHANNELS[0], SlackNotificationChannel)
    assert isinstance(NOTIFICATION_CHANNELS[1], SmtpNotificationChannel)

@patch("app.services.notification.slack.httpx.post")
def test_slack_notifier_real_post(mock_post):
    mock_db = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    with patch("app.services.notification.slack.settings") as mock_slack_settings:
        mock_slack_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/test"
        channel = SlackNotificationChannel()
        channel.send_message("Slack Alert", "Hello!", mock_db)

        mock_post.assert_called_once_with(
            "https://hooks.slack.com/services/test",
            json={"text": "*Slack Alert*\nHello!"}
        )
        mock_resp.raise_for_status.assert_called_once()

@patch("app.services.notification.slack.httpx.post")
def test_slack_notifier_raises_exception(mock_post):
    mock_db = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock())
    mock_post.return_value = mock_resp

    with patch("app.services.notification.slack.settings") as mock_slack_settings:
        mock_slack_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/test"
        channel = SlackNotificationChannel()
        with pytest.raises(httpx.HTTPStatusError):
            channel.send_message("Slack Alert", "Hello!", mock_db)

def test_smtp_notifier_raises_exception():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = ["admin@example.com"]

    with patch("app.services.notification.smtp.settings") as mock_settings, \
         patch("app.services.notification.smtp.smtplib.SMTP", side_effect=Exception("SMTP Connection Error")):
        mock_settings.SMTP_HOST = "smtp.mail.com"
        mock_settings.SMTP_PORT = 587
        
        channel = SmtpNotificationChannel()
        with pytest.raises(Exception) as exc:
            channel.send_message("SMTP Alert", "Hello!", mock_db, details={"topic": "job-failed"})
        assert "SMTP Connection Error" in str(exc.value)

def test_subscriber_message_routing_completed():
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = ["admin@example.com"]

    job_id = uuid.uuid4()
    source_id = uuid.uuid4()
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id)
    }

    with patch("app.services.notification.smtp.smtplib.SMTP") as mock_smtp, \
         patch("app.services.notification.slack.settings") as mock_slack_settings, \
         patch("app.services.notification.smtp.settings") as mock_smtp_settings:
         
        mock_smtp_settings.SMTP_HOST = "smtp.test.com"
        mock_smtp_settings.SMTP_PORT = 587
        mock_smtp_settings.SMTP_USER = "user"
        mock_smtp_settings.SMTP_PASSWORD = "password"
        mock_smtp_settings.NOTIFICATION_EMAIL_SENDER = "no-reply@test.com"
        mock_slack_settings.SLACK_WEBHOOK_URL = None
        
        process_notification("job-completed", payload, mock_db)
        mock_smtp.assert_called_once()


@patch("app.services.notification.slack.httpx.post")
def test_slack_webhook_routing(mock_post):
    mock_db = MagicMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_post.return_value = mock_resp

    with patch("app.services.notification.slack.settings") as mock_settings:
        mock_settings.SLACK_WEBHOOK_URL = "https://default-webhook"
        mock_settings.SLACK_WEBHOOK_DEAD_LETTER = "https://dlq-webhook"
        mock_settings.SLACK_WEBHOOK_JOB_FAILED = "https://failed-webhook"
        mock_settings.SLACK_WEBHOOK_JOB_COMPLETED = "https://completed-webhook"
        mock_settings.SLACK_WEBHOOK_NEW_TABLE = "https://new-table-webhook"

        channel = SlackNotificationChannel()

        # 1. Dead Letter
        channel.send_message("DLQ", "Message", mock_db, details={"topic": "dead-letter"})
        mock_post.assert_called_with("https://dlq-webhook", json={"text": "*DLQ*\nMessage"})

        # 2. Job Failed
        channel.send_message("Failed", "Message", mock_db, details={"topic": "job-failed"})
        mock_post.assert_called_with("https://failed-webhook", json={"text": "*Failed*\nMessage"})

        # 3. Job Completed
        channel.send_message("Completed", "Message", mock_db, details={"topic": "job-completed"})
        mock_post.assert_called_with("https://completed-webhook", json={"text": "*Completed*\nMessage"})

        # 4. Fallback requested / New table
        channel.send_message("New Table", "Message", mock_db, details={"topic": "fallback-requested"})
        mock_post.assert_called_with("https://new-table-webhook", json={"text": "*New Table*\nMessage"})

        # 5. Default fallback
        channel.send_message("Generic", "Message", mock_db, details={"topic": "unknown-topic"})
        mock_post.assert_called_with("https://default-webhook", json={"text": "*Generic*\nMessage"})
