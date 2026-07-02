import time
import json
import logging
from google.cloud import pubsub_v1

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
    from workers.common.dummy_server import start_dummy_server
    start_dummy_server()
    while True:
        subscriber = None
        drift_future = None
        try:
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

            logger.info("Schema Drift Worker started. Listening on schema-validated subscriptions...")
            
            # Non-blocking poll loop to allow clean KeyboardInterrupt handling
            while drift_future.running():
                time.sleep(1)
                
            if drift_future.done() and drift_future.exception():
                drift_future.result()

        except KeyboardInterrupt:
            logger.info("Schema Drift Worker stopped by user.")
            if drift_future:
                try:
                    drift_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Schema Drift Subscriber encountered an error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            if drift_future:
                try:
                    drift_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)
