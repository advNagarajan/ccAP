import time
import json
import asyncio
import logging
from uuid import UUID
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.vectorizers.target_vectorizer.processor import (
    sync_target_vector_on_mutation,
    append_feedback_and_revectorize
)

from workers.common.retry_handler import handle_worker_failure, reset_retry_count

logger = logging.getLogger("target_vectorizer")


def callback_mutation(message):
    raw_data = ""
    db = SessionLocal()
    try:
        logger.info(f"Received mutation message: {message.message_id}")
        raw_data = message.data.decode("utf-8")
        payload = json.loads(raw_data)
        
        if not isinstance(payload, dict) or "target_id" not in payload:
            logger.warning(f"Message {message.message_id} is missing target_id or is not a JSON object. Discarding.")
            message.ack()
            return

        target_id = payload["target_id"]
        try:
            UUID(str(target_id))
        except ValueError:
            logger.warning(f"Message {message.message_id} has badly formed UUID '{target_id}'. Discarding.")
            message.ack()
            return

        # Execute async pipeline in event loop
        asyncio.run(sync_target_vector_on_mutation(target_id, db))
        message.ack()
        logger.info(f"Acknowledged mutation message: {message.message_id}")

    except json.JSONDecodeError:
        logger.warning(f"Message {message.message_id} payload is not valid JSON. Discarding.")
        message.ack()
    except Exception as e:
        logger.error(f"Failed to process mutation message: {e}")
        handle_worker_failure(
            job_id=None,
            worker_name="target_vectorizer_mutation",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def callback_feedback(message):
    raw_data = ""
    db = SessionLocal()
    job_id = None
    try:
        logger.info(f"Received feedback message: {message.message_id}")
        raw_data = message.data.decode("utf-8")
        payload = json.loads(raw_data)
        
        if not isinstance(payload, dict) or "job_id" not in payload or "target_id" not in payload or "user_action" not in payload:
            logger.warning(f"Message {message.message_id} is missing required fields. Discarding.")
            message.ack()
            return

        job_id = payload["job_id"]
        target_id = payload["target_id"]
        user_action = payload["user_action"]
        notes = payload.get("notes") or ""

        try:
            UUID(str(job_id))
            UUID(str(target_id))
        except ValueError:
            logger.warning(f"Message {message.message_id} has badly formed UUIDs. Discarding.")
            message.ack()
            return

        asyncio.run(
            append_feedback_and_revectorize(
                job_id=job_id,
                target_id=target_id,
                user_action=user_action,
                notes=notes,
                db=db
            )
        )
        reset_retry_count(job_id, db)
        message.ack()
        logger.info(f"Acknowledged feedback message: {message.message_id}")

    except json.JSONDecodeError:
        logger.warning(f"Message {message.message_id} payload is not valid JSON. Discarding.")
        message.ack()
    except Exception as e:
        logger.error(f"Failed to process feedback message: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="target_vectorizer_feedback",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    while True:
        subscriber = None
        mutation_future = None
        feedback_future = None
        try:
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

            logger.info("Target Vectorizer Workers started. Listening on subscriptions...")
            
            # Poll both futures to make sure they are running
            while mutation_future.running() and feedback_future.running():
                time.sleep(1)
                
            # If any future stopped, retrieve its exception
            if mutation_future.done() and mutation_future.exception():
                mutation_future.result()
            if feedback_future.done() and feedback_future.exception():
                feedback_future.result()

        except KeyboardInterrupt:
            logger.info("Target Vectorizer Workers stopped by user.")
            for f in (mutation_future, feedback_future):
                if f:
                    try:
                        f.cancel()
                    except Exception:
                        pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            logger.error(f"Target Vectorizer Subscriber encountered an error: {e}. Reconnecting in 10 seconds...", exc_info=True)
            for f in (mutation_future, feedback_future):
                if f:
                    try:
                        f.cancel()
                    except Exception:
                        pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)
