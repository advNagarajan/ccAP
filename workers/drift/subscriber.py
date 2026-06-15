import json
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.drift.processor import process_schema_drift

logger = logging.getLogger("schema_drift")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_schema_validated(message):
    try:
        logger.info(f"Received schema validated message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        validation_id = payload["validation_id"]

        db = SessionLocal()
        try:
            # Execute schema drift processing
            process_schema_drift(
                job_id=job_id,
                artifact_id=artifact_id,
                validation_id=validation_id,
                db=db
            )
            message.ack()
            logger.info(f"Acknowledged schema validated message: {message.message_id}")
        except ValueError as ve:
            if "SchemaValidation not found" in str(ve):
                logger.warning(f"Discarding poison-pill message because database record was rolled back/not found: {ve}")
                message.ack()
            else:
                raise
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process schema validated message: {e}")
        message.nack()


def start_subscriber():
    subscriber = pubsub_v1.SubscriberClient()

    drift_sub_path = subscriber.subscription_path(
        settings.GCP_PROJECT_ID,
        settings.PUBSUB_SUBSCRIPTION_SCHEMA_VALIDATED
    )

    logger.info(f"Subscribing to schema validated: {drift_sub_path}")
    drift_future = subscriber.subscribe(
        drift_sub_path,
        callback=callback_schema_validated
    )

    try:
        logger.info("Schema Drift Worker started. Listening on schema-validated subscriptions...")
        drift_future.result()
    except KeyboardInterrupt:
        drift_future.cancel()
        logger.info("Schema Drift Worker stopped.")
