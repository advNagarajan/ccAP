import json

from google.cloud import pubsub_v1

from app.core.settings import settings


publisher = pubsub_v1.PublisherClient()

topic_path = publisher.topic_path(
    settings.GCP_PROJECT_ID,
    settings.PUBSUB_TOPIC_INGESTION_REQUESTED
)


def publish_ingestion_requested(
    job_id,
    source_id
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id)
    }

    future = publisher.publish(
        topic_path,
        json.dumps(payload).encode("utf-8")
    )

    message_id = future.result()

    print(
        f"Published ingestion-requested "
        f"message_id={message_id}"
    )

    return message_id