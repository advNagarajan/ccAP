from google.cloud import pubsub_v1

from app.core.settings import settings
from workers.ingestion.processor import process_ingestion_requested


subscriber = pubsub_v1.SubscriberClient()

subscription_path = subscriber.subscription_path(
    settings.GCP_PROJECT_ID,
    settings.PUBSUB_SUBSCRIPTION_INGESTION_REQUESTED
)


def callback(message):
    try:
        print(f"Received message: {message.message_id}")

        process_ingestion_requested(message.data)

        message.ack()

        print(f"Acknowledged message: {message.message_id}")

    except Exception as e:
        print(f"Message processing failed: {e}")

        message.nack()


def start_subscriber():
    streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback) 

    print(f"Listening on {subscription_path}")

    try:
        streaming_pull_future.result()

    except KeyboardInterrupt:
        streaming_pull_future.cancel()

        print("Subscriber stopped")