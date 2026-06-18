import logging
import time
from sqlalchemy.orm import Session
from app.services.notification.registry import NOTIFICATION_CHANNELS

logger = logging.getLogger("notification_worker")


def process_notification(topic: str, payload: dict, db: Session) -> None:
    """
    Core processor logic for distributing notification messages across registered channels.
    """
    job_id = payload.get("job_id")
    source_id = payload.get("source_id")

    subject = f"System Event: {topic.upper()}"
    message = f"Job ID: {job_id}\nSource ID: {source_id}\n"

    if topic == "dead-letter":
        subject = "CRITICAL: Job Failed & Hit Dead Letter Queue"
        failed_worker = payload.get("failed_at_worker")
        error = payload.get("error_message")
        attempt = payload.get("attempt_number")
        message += f"Failed Worker: {failed_worker}\nAttempt Number: {attempt}\nError: {error}"
    elif topic == "job-failed":
        subject = "Alert: Job Processing Failed"
        error = payload.get("error_message")
        message += f"Error Details: {error}"
    elif topic == "job-completed":
        subject = "Success: Job Processing Completed Successfully"
        rec_count = payload.get("recommendations_count", 0)
        target_name = payload.get("target_name")
        message += "The landing and inference job finished without errors.\n"
        if target_name:
            message += f"Target Table: {target_name}\n"
        message += f"Recommendations Generated: {rec_count}"
    elif topic == "fallback-landing-created":
        subject = "Notice: Fallback Landing Schema Created"
        backup_table = payload.get("backup_table_name")
        message += f"Drift validation fallback table created: {backup_table}"

    for channel in NOTIFICATION_CHANNELS:
        max_attempts = 3
        backoff = 2  # base delay in seconds
        for attempt in range(1, max_attempts + 1):
            try:
                channel.send_message(subject, message, db, details=payload)
                break
            except Exception as channel_err:
                if attempt == max_attempts:
                    logger.error(
                        f"Channel {channel.__class__.__name__} failed permanently after {max_attempts} attempts: {channel_err}"
                    )
                else:
                    sleep_time = backoff ** attempt
                    logger.warning(
                        f"Channel {channel.__class__.__name__} failed (attempt {attempt}/{max_attempts}): {channel_err}. Retrying in {sleep_time}s..."
                    )
                    time.sleep(sleep_time)
