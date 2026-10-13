import time
import json
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.validation.processor import process_schema_validation

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("schema_validation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_target_inferred(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received target inferred message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        metadata_profile_id = payload["metadata_profile_id"]
        inference_id = payload["inference_id"]

        try:
            # Execute synchronous validation pipeline
            process_schema_validation(
                job_id=job_id,
                artifact_id=artifact_id,
                metadata_profile_id=metadata_profile_id,
                inference_id=inference_id,
                db=db
            )
            reset_retry_count(job_id, db)
            message.ack()
            logger.info(f"Acknowledged target inferred message: {message.message_id}")
        except ValueError as ve:
            if "LandingInference not found" in str(ve):
                logger.warning(f"Discarding poison-pill message because database record was rolled back/not found: {ve}")
                message.ack()
            else:
                raise

    except Exception as e:
        logger.error(f"Failed to process target inferred message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="schema_validation",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    from workers.common.runner import run_worker_subscriber
    run_worker_subscriber(
        topic_name=settings.PUBSUB_TOPIC_TARGET_INFERRED,
        subscription_name=settings.PUBSUB_SUBSCRIPTION_TARGET_INFERRED,
        callback_fn=callback_target_inferred,
        worker_name="schema_validation"
    )

