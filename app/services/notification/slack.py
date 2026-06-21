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
        topic = details.get("topic") if details else None

        if topic == "dead-letter":
            webhook_url = settings.SLACK_WEBHOOK_DEAD_LETTER or settings.SLACK_WEBHOOK_URL
        elif topic == "job-failed":
            webhook_url = settings.SLACK_WEBHOOK_JOB_FAILED or settings.SLACK_WEBHOOK_URL
        elif topic == "job-completed":
            webhook_url = settings.SLACK_WEBHOOK_JOB_COMPLETED or settings.SLACK_WEBHOOK_URL
        elif topic in ("fallback-landing-created", "fallback-requested"):
            webhook_url = settings.SLACK_WEBHOOK_NEW_TABLE or settings.SLACK_WEBHOOK_URL
        else:
            webhook_url = settings.SLACK_WEBHOOK_URL

        if not webhook_url:
            logger.warning(
                f"[STUB] Slack Notification: '{subject}' -> {message}. "
                "SLACK_WEBHOOK_URL is not configured."
            )
            return

        logger.info(
            f"Posting Slack Notification: '{subject}' to {webhook_url}"
        )
        response = httpx.post(webhook_url, json={"text": f"*{subject}*\n{message}"})
        response.raise_for_status()
