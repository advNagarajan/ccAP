import json
import asyncio
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.inference.processor import infer_target_landing_zone

logger = logging.getLogger("landing_inference")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def callback_metadata_vectorized(message):
    try:
        logger.info(f"Received metadata vectorized message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        artifact_id = payload["artifact_id"]
        metadata_profile_id = payload["metadata_profile_id"]

        db = SessionLocal()
        try:
            asyncio.run(infer_target_landing_zone(job_id, artifact_id, metadata_profile_id, db))
            message.ack()
            logger.info(f"Acknowledged metadata vectorized message: {message.message_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process metadata vectorized message: {e}")
        message.nack()


def start_subscriber():
    subscriber = pubsub_v1.SubscriberClient()

    sub_path = subscriber.subscription_path(
        settings.GCP_PROJECT_ID,
        settings.PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED
    )

    logger.info(f"Subscribing to metadata vectorized: {sub_path}")
    future = subscriber.subscribe(
        sub_path,
        callback=callback_metadata_vectorized
    )

    try:
        logger.info("Target Inference Worker started. Listening on subscriptions...")
        future.result()
    except KeyboardInterrupt:
        future.cancel()
        logger.info("Target Inference Worker stopped.")
