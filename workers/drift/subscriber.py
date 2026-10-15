import time
import json
import logging
try:
    from google.cloud import pubsub_v1
except ImportError:
    pubsub_v1 = None

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.drift.processor import process_schema_drift

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("schema_drift")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_schema_validated(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received schema validated message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        validation_id = payload["validation_id"]

        try:
            # Execute schema drift processing
            process_schema_drift(
                job_id=job_id,
                artifact_id=artifact_id,
                validation_id=validation_id,
                db=db
            )
            reset_retry_count(job_id, db)
            message.ack()
            logger.info(f"Acknowledged schema validated message: {message.message_id}")
        except ValueError as ve:
            if "SchemaValidation not found" in str(ve):
                logger.warning(f"Discarding poison-pill message because database record was rolled back/not found: {ve}")
                message.ack()
            else:
                raise

    except Exception as e:
        logger.error(f"Failed to process schema validated message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="schema_drift",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    from workers.common.runner import run_worker_subscriber
    run_worker_subscriber(
        topic_name=settings.PUBSUB_TOPIC_SCHEMA_VALIDATED,
        subscription_name=settings.PUBSUB_SUBSCRIPTION_SCHEMA_VALIDATED,
        callback_fn=callback_schema_validated,
        worker_name="schema_drift"
    )

