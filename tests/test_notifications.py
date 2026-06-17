import uuid
from unittest.mock import MagicMock, patch
import pytest

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

    # Set up active recipients in the mock database query
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
            details={"key": "val"}
        )

        # Verify database select was performed
        mock_db.execute.assert_called_once()
        
        # Verify smtplib interactions occurred
        mock_smtp_cls.assert_called_once_with("smtp.mail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test", "pwd")
        mock_server.sendmail.assert_called_once()


def test_slack_notifier_stub_no_crash():
    mock_db = MagicMock()
    channel = SlackNotificationChannel()
    
    # Slack is a stub, so it should log warnings/info and exit cleanly
    channel.send_message("Slack test", "Hello Slack!", mock_db)
    
    # Assert registry lists both channels
    assert len(NOTIFICATION_CHANNELS) == 2
    assert isinstance(NOTIFICATION_CHANNELS[0], SlackNotificationChannel)
    assert isinstance(NOTIFICATION_CHANNELS[1], SmtpNotificationChannel)


def test_subscriber_message_routing_completed():
    mock_db = MagicMock()
    
    # Mock active recipients
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
        mock_slack_settings.SLACK_WEBHOOK_URL = None
        
        # Run event routing helper
        process_notification("job-completed", payload, mock_db)
        
        # Ensure smtplib sent email
        mock_smtp.assert_called_once()
