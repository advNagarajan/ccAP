import json
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.ingestion.processor import process_ingestion_requested
from workers.common.retry_handler import handle_worker_failure, reset_retry_count

subscriber = pubsub_v1.SubscriberClient()

subscription_path = subscriber.subscription_path(
    settings.GCP_PROJECT_ID,
    settings.PUBSUB_SUBSCRIPTION_INGESTION_REQUESTED
)


def callback(message):
    db = SessionLocal()
    job_id = None
    try:
        print(f"Received message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload.get("job_id")

        process_ingestion_requested(message.data)

        reset_retry_count(job_id, db)
        message.ack()

        print(f"Acknowledged message: {message.message_id}")

    except Exception as e:
        print(f"Message processing failed: {e}")
        handle_worker_failure(
            job_id=job_id,
            worker_name="ingestion",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback) 

    print(f"Listening on {subscription_path}")

    try:
        streaming_pull_future.result()

    except KeyboardInterrupt:
        streaming_pull_future.cancel()

        print("Subscriber stopped")