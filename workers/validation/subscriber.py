import json
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.validation.processor import process_schema_validation

logger = logging.getLogger("schema_validation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_target_inferred(message):
    try:
        logger.info(f"Received target inferred message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        metadata_profile_id = payload["metadata_profile_id"]
        inference_id = payload["inference_id"]

        db = SessionLocal()
        try:
            # Execute synchronous validation pipeline
            process_schema_validation(
                job_id=job_id,
                artifact_id=artifact_id,
                metadata_profile_id=metadata_profile_id,
                inference_id=inference_id,
                db=db
            )
            message.ack()
            logger.info(f"Acknowledged target inferred message: {message.message_id}")
        except ValueError as ve:
            if "LandingInference not found" in str(ve):
                logger.warning(f"Discarding poison-pill message because database record was rolled back/not found: {ve}")
                message.ack()
            else:
                raise
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process target inferred message: {e}")
        message.nack()


def start_subscriber():
    subscriber = pubsub_v1.SubscriberClient()

    validation_sub_path = subscriber.subscription_path(
        settings.GCP_PROJECT_ID,
        settings.PUBSUB_SUBSCRIPTION_TARGET_INFERRED
    )

    logger.info(f"Subscribing to target inferred: {validation_sub_path}")
    validation_future = subscriber.subscribe(
        validation_sub_path,
        callback=callback_target_inferred
    )

    try:
        logger.info("Schema Validation Worker started. Listening on target-inferred subscriptions...")
        validation_future.result()
    except KeyboardInterrupt:
        validation_future.cancel()
        logger.info("Schema Validation Worker stopped.")
