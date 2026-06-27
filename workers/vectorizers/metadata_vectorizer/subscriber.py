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
    while True:
        subscriber = None
        metadata_future = None
        try:
            subscriber = pubsub_v1.SubscriberClient()

            metadata_sub_path = subscriber.subscription_path(
                settings.GCP_PROJECT_ID,
                settings.PUBSUB_SUBSCRIPTION_METADATA_EXTRACTED
            )

            logger.info(f"Subscribing to metadata extracted: {metadata_sub_path}")
            metadata_future = subscriber.subscribe(
                metadata_sub_path,
                callback=callback_metadata_extracted
            )

            # Keep main thread alive while future runs in background threads
            logger.info("Metadata Vectorizer Worker started. Listening on subscriptions...")
            
            while metadata_future.running():
                time.sleep(1)
                
            if metadata_future.done() and metadata_future.exception():
                metadata_future.result()

        except KeyboardInterrupt:
            logger.info("Metadata Vectorizer Worker stopped by user.")
            if metadata_future:
                try:
                    metadata_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Metadata Vectorizer Subscriber encountered an error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            if metadata_future:
                try:
                    metadata_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)
