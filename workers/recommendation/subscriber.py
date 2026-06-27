import time
import json
import logging
import asyncio
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.recommendation.processor import process_schema_recommendation

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("schema_recommendation")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_drift_detected(message):
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received drift detected message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        drift_id = payload["drift_id"]

        try:
            # Run the async processor synchronously using asyncio.run
            asyncio.run(
                process_schema_recommendation(
                    job_id=job_id,
                    artifact_id=artifact_id,
                    drift_id=drift_id,
                    db=db
                )
            )
            reset_retry_count(job_id, db)
            message.ack()
            logger.info(f"Acknowledged drift detected message: {message.message_id}")
        except ValueError as ve:
            if "SchemaDrift not found" in str(ve) or "SchemaValidation not found" in str(ve):
                logger.warning(f"Discarding poison-pill message: {ve}")
                message.ack()
            else:
                raise

    except Exception as e:
        logger.error(f"Failed to process drift detected message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="schema_recommendation",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    while True:
        subscriber = None
        rec_future = None
        try:
            subscriber = pubsub_v1.SubscriberClient()

            rec_sub_path = subscriber.subscription_path(
                settings.GCP_PROJECT_ID,
                settings.PUBSUB_SUBSCRIPTION_DRIFT_DETECTED
            )

            logger.info(f"Subscribing to drift detected: {rec_sub_path}")
            rec_future = subscriber.subscribe(
                rec_sub_path,
                callback=callback_drift_detected
            )

            logger.info("Schema Recommendation Worker started. Listening on drift-detected subscriptions...")
            
            # Non-blocking poll loop to allow clean KeyboardInterrupt handling
            while rec_future.running():
                time.sleep(1)
                
            if rec_future.done() and rec_future.exception():
                rec_future.result()

        except KeyboardInterrupt:
            logger.info("Schema Recommendation Worker stopped by user.")
            if rec_future:
                try:
                    rec_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Schema Recommendation Subscriber encountered an error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            if rec_future:
                try:
                    rec_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)
