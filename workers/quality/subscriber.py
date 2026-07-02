import time
import json
import logging
from google.cloud import pubsub_v1

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
    from workers.common.dummy_server import start_dummy_server
    start_dummy_server()
    while True:
        subscriber = None
        quality_future = None
        try:
            subscriber = pubsub_v1.SubscriberClient()

            quality_sub_path = subscriber.subscription_path(
                settings.GCP_PROJECT_ID,
                settings.PUBSUB_SUBSCRIPTION_QUALITY_CHECK_REQUESTED
            )

            logger.info(f"Subscribing to quality check requested: {quality_sub_path}")
            quality_future = subscriber.subscribe(
                quality_sub_path,
                callback=callback_quality_check_requested
            )

            logger.info("Data Quality Worker started. Listening on quality-check-requested subscriptions...")
            
            while quality_future.running():
                time.sleep(1)
                
            if quality_future.done() and quality_future.exception():
                quality_future.result()

        except KeyboardInterrupt:
            logger.info("Data Quality Worker stopped by user.")
            if quality_future:
                try:
                    quality_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Data Quality Subscriber encountered an error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            if quality_future:
                try:
                    quality_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)
