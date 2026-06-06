from google.cloud import pubsub_v1

from app.core.settings import settings
from workers.metadata.processor import process_dataset_received


subscriber = pubsub_v1.SubscriberClient()

subscription_path = subscriber.subscription_path(
    settings.GCP_PROJECT_ID,
    settings.PUBSUB_SUBSCRIPTION_DATASET_RECEIVED
)


def callback(message):

    try:

        print(f"Received message: {message.message_id}")

        process_dataset_received(
            message.data
        )

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

        message.nack()


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