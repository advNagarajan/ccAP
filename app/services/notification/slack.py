import logging
import httpx
from sqlalchemy.orm import Session
from app.services.notification.base import BaseNotificationChannel
from app.core.settings import settings

logger = logging.getLogger("slack_notifier")

class SlackNotificationChannel(BaseNotificationChannel):

    def send_message(
        self,
        subject: str,
        message: str,
        db: Session,
        details: dict = None
    ) -> None:
        webhook_url = settings.SLACK_WEBHOOK_URL
        if not webhook_url:
            logger.warning(
                f"[STUB] Slack Notification: '{subject}' -> {message}. "
                "SLACK_WEBHOOK_URL is not configured."
            )
            return

        logger.info(
            f"Posting Slack Notification: '{subject}'"
        )
        response = httpx.post(webhook_url, json={"text": f"*{subject}*\n{message}"})
        response.raise_for_status()
