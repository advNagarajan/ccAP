import json
import asyncio
import logging
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.vectorizers.target_vectorizer.processor import (
    sync_target_vector_on_mutation,
    append_feedback_and_revectorize
)

logger = logging.getLogger("vector_sync")


def callback_mutation(message):
    try:
        logger.info(f"Received mutation message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        target_id = payload["target_id"]

        db = SessionLocal()
        try:
            # Execute async pipeline in event loop
            asyncio.run(sync_target_vector_on_mutation(target_id, db))
            message.ack()
            logger.info(f"Acknowledged mutation message: {message.message_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process mutation message: {e}")
        message.nack()


def callback_feedback(message):
    try:
        logger.info(f"Received feedback message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload["job_id"]
        target_id = payload["target_id"]
        user_action = payload["user_action"]
        notes = payload.get("notes") or ""

        db = SessionLocal()
        try:
            asyncio.run(
                append_feedback_and_revectorize(
                    job_id=job_id,
                    target_id=target_id,
                    user_action=user_action,
                    notes=notes,
                    db=db
                )
            )
            message.ack()
            logger.info(f"Acknowledged feedback message: {message.message_id}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to process feedback message: {e}")
        message.nack()


def start_subscriber():
    subscriber = pubsub_v1.SubscriberClient()

    mutation_sub_path = subscriber.subscription_path(
        settings.GCP_PROJECT_ID,
        settings.PUBSUB_SUBSCRIPTION_TARGET_MUTATED
    )
    feedback_sub_path = subscriber.subscription_path(
        settings.GCP_PROJECT_ID,
        settings.PUBSUB_SUBSCRIPTION_FEEDBACK_SUBMITTED
    )

    logger.info(f"Subscribing to target mutation: {mutation_sub_path}")
    mutation_future = subscriber.subscribe(
        mutation_sub_path,
        callback=callback_mutation
    )

    logger.info(f"Subscribing to feedback loop: {feedback_sub_path}")
    feedback_future = subscriber.subscribe(
        feedback_sub_path,
        callback=callback_feedback
    )

    try:
        # Keep main thread alive while futures run in background threads
        # We can just wait for both results
        # To avoid blocking indefinitely on one, we can run a loop or just wait on one
        logger.info("Vector Sync Workers started. Listening on subscriptions...")
        mutation_future.result()
    except KeyboardInterrupt:
        mutation_future.cancel()
        feedback_future.cancel()
        logger.info("Vector Sync Workers stopped.")
