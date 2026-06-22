import json
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.notification.processor import process_notification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification_worker")

subscriber = pubsub_v1.SubscriberClient()

def make_callback(topic_name: str):
    def callback(message):
        db = SessionLocal()
        try:
            logger.info(f"Received message on {topic_name}: {message.message_id}")
            payload = json.loads(message.data.decode("utf-8"))
            process_notification(topic_name, payload, db)
            message.ack()
        except Exception as e:
            logger.error(f"Failed to process notification message for {topic_name}: {e}")
            message.nack()
        finally:
            db.close()
    return callback

def start_subscriber():
    subscriptions = {
        "job-completed": settings.PUBSUB_SUBSCRIPTION_JOB_COMPLETED,
        "job-failed": settings.PUBSUB_SUBSCRIPTION_JOB_FAILED,
        "fallback-requested": settings.PUBSUB_SUBSCRIPTION_FALLBACK_REQUESTED,
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
    
    try:
        # Block and wait for termination
        for future in futures:
            try:
                future.result()
            except Exception as e:
                logger.error(f"Error in subscriber future: {e}")
    except KeyboardInterrupt:
        logger.info("Stopping notification subscriber...")
        for future in futures:
            future.cancel()
        logger.info("Subscriber stopped")

