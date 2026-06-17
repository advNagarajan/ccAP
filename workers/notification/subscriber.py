import json
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from app.services.notification.registry import NOTIFICATION_CHANNELS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_worker")

subscriber = pubsub_v1.SubscriberClient()

# Helper to process and format messages
def handle_notification_message(topic: str, data: bytes):
    payload = json.loads(data.decode("utf-8"))
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
        message += "The landing and inference job finished without errors."
    elif topic == "fallback-landing-created":
        subject = "Notice: Fallback Landing Schema Created"
        backup_table = payload.get("backup_table_name")
        message += f"Drift validation fallback table created: {backup_table}"

    db = SessionLocal()
    try:
        for channel in NOTIFICATION_CHANNELS:
            try:
                channel.send_message(subject, message, db, details=payload)
            except Exception as channel_err:
                logger.error(f"Channel {channel.__class__.__name__} failed to send message: {channel_err}")
    finally:
        db.close()

def make_callback(topic_name: str):
    def callback(message):
        try:
            logger.info(f"Received message on {topic_name}: {message.message_id}")
            handle_notification_message(topic_name, message.data)
            message.ack()
        except Exception as e:
            logger.error(f"Failed to process notification message for {topic_name}: {e}")
            message.nack()
    return callback

def start_subscriber():
    subscriptions = {
        "job-completed": settings.PUBSUB_SUBSCRIPTION_JOB_COMPLETED,
        "job-failed": settings.PUBSUB_SUBSCRIPTION_JOB_FAILED,
        "fallback-landing-created": settings.PUBSUB_SUBSCRIPTION_FALLBACK_LANDING_CREATED,
        "dead-letter": settings.PUBSUB_SUBSCRIPTION_DEAD_LETTER
    }

    futures = []
    for topic_name, sub_name in subscriptions.items():
        if not sub_name:
            logger.warning(f"Subscription for {topic_name} is not configured. Skipping.")
            continue
            
        sub_path = subscriber.subscription_path(settings.GCP_PROJECT_ID, sub_name)
        logger.info(f"Subscribing to subscription path: {sub_path}")
        future = subscriber.subscribe(sub_path, callback=make_callback(topic_name))
        futures.append(future)

    logger.info("Notification subscriber started successfully. Listening for events...")
    
    # Block and wait for termination
    for future in futures:
        try:
            future.result()
        except Exception as e:
            logger.error(f"Error in subscriber future: {e}")

