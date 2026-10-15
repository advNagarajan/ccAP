import time
import json
import logging
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.metadata.processor import process_dataset_received
from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("metadata_extraction")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload.get("job_id")

        process_dataset_received(
            message.data
        )

        reset_retry_count(job_id, db)
        message.ack()

        logger.info(f"Acknowledged message: {message.message_id}")

    except Exception as e:
        logger.error(f"Message processing failed: {e}", exc_info=True)
        handle_worker_failure(
            job_id=job_id,
            worker_name="metadata_extraction",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    from workers.common.runner import run_worker_subscriber
    run_worker_subscriber(
        topic_name=settings.PUBSUB_TOPIC_DATASET_RECEIVED,
        subscription_name=settings.PUBSUB_SUBSCRIPTION_DATASET_RECEIVED,
        callback_fn=callback,
        worker_name="metadata_extraction"
    )