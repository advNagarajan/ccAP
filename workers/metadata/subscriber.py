import json
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.metadata.processor import process_dataset_received
from workers.common.retry_handler import handle_worker_failure, reset_retry_count

subscriber = pubsub_v1.SubscriberClient()

subscription_path = subscriber.subscription_path(
    settings.GCP_PROJECT_ID,
    settings.PUBSUB_SUBSCRIPTION_DATASET_RECEIVED
)


def callback(message):
    db = SessionLocal()
    job_id = None
    try:
        print(f"Received message: {message.message_id}")
        payload = json.loads(message.data.decode("utf-8"))
        job_id = payload.get("job_id")

        process_dataset_received(
            message.data
        )

        reset_retry_count(job_id, db)
        message.ack()

        print(
            f"Acknowledged message: "
            f"{message.message_id}"
        )

    except Exception as e:
        print(
            f"Message processing failed: "
            f"{e}"
        )
        handle_worker_failure(
            job_id=job_id,
            worker_name="metadata_extraction",
            error=e,
            message=message,
            db=db
        )
    finally:
        db.close()


def start_subscriber():

    streaming_pull_future = subscriber.subscribe(
        subscription_path,
        callback=callback
    )

    print(
        f"Listening on "
        f"{subscription_path}"
    )

    try:

        streaming_pull_future.result()

    except KeyboardInterrupt:

        streaming_pull_future.cancel()

        print("Subscriber stopped")