import time
import json
import asyncio
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.vectorizers.metadata_vectorizer.processor import (
    sync_metadata_vector
)

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("metadata_vectorizer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_metadata_extracted(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received metadata extracted message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        metadata_profile_id = payload["metadata_profile_id"]

        # Execute async pipeline in event loop
        asyncio.run(sync_metadata_vector(job_id, artifact_id, metadata_profile_id, db))
        reset_retry_count(job_id, db)
        message.ack()
        logger.info(f"Acknowledged metadata extracted message: {message.message_id}")

    except Exception as e:
        logger.error(f"Failed to process metadata extracted message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="metadata_vectorizer",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    from workers.common.runner import run_worker_subscriber
    run_worker_subscriber(
        topic_name=settings.PUBSUB_TOPIC_METADATA_EXTRACTED,
        subscription_name=settings.PUBSUB_SUBSCRIPTION_METADATA_EXTRACTED,
        callback_fn=callback_metadata_extracted,
        worker_name="metadata_vectorizer"
    )

