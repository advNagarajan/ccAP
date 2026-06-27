import time
import json
from google.cloud import pubsub_v1

from app.core.settings import settings
from app.db.database import SessionLocal
from workers.metadata.processor import process_dataset_received
from workers.common.retry_handler import handle_worker_failure, reset_retry_count


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
    while True:
        subscriber = None
        streaming_pull_future = None
        try:
            subscriber = pubsub_v1.SubscriberClient()
            subscription_path = subscriber.subscription_path(
                settings.GCP_PROJECT_ID,
                settings.PUBSUB_SUBSCRIPTION_DATASET_RECEIVED
            )

            streaming_pull_future = subscriber.subscribe(
                subscription_path,
                callback=callback
            )

            print(
                f"Listening on "
                f"{subscription_path}"
            )

            while streaming_pull_future.running():
                time.sleep(1)

            if streaming_pull_future.done() and streaming_pull_future.exception():
                streaming_pull_future.result()

        except KeyboardInterrupt:
            print("Subscriber stopped")
            if streaming_pull_future:
                try:
                    streaming_pull_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            break
        except Exception as e:
            print(f"Metadata Extraction Subscriber encountered an error: {e}. Reconnecting in 10 seconds...")
            if streaming_pull_future:
                try:
                    streaming_pull_future.cancel()
                except Exception:
                    pass
            if subscriber:
                try:
                    subscriber.close()
                except Exception:
                    pass
            time.sleep(10)