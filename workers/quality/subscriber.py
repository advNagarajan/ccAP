import time
import json
import logging
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.quality.processor import process_data_quality

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("data_quality")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_quality_check_requested(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received quality check requested message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        parent_job_id = payload["parent_job_id"]
        source_id = payload["source_id"]
        artifact_id = payload["artifact_id"]

        process_data_quality(
            job_id=job_id,
            parent_job_id=parent_job_id,
            source_id=source_id,
            artifact_id=artifact_id,
            db=db
        )
        reset_retry_count(job_id, db)
        message.ack()
        logger.info(f"Acknowledged quality check requested message: {message.message_id}")

    except Exception as e:
        logger.error(f"Failed to process quality check message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="data_quality",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    from workers.common.runner import run_worker_subscriber
    run_worker_subscriber(
        topic_name=settings.PUBSUB_TOPIC_QUALITY_CHECK_REQUESTED,
        subscription_name=settings.PUBSUB_SUBSCRIPTION_QUALITY_CHECK_REQUESTED,
        callback_fn=callback_quality_check_requested,
        worker_name="data_quality"
    )

