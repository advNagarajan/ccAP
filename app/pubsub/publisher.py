import json

from google.cloud import pubsub_v1

from app.core.settings import settings


publisher = pubsub_v1.PublisherClient()


def publish_event(topic_name: str, payload: dict):
    topic_path = publisher.topic_path(
        settings.GCP_PROJECT_ID,
        topic_name
    )

    future = publisher.publish(
        topic_path,
        json.dumps(payload).encode("utf-8")
    )

    message_id = future.result()

    print(
        f"Published {topic_name} "
        f"message_id={message_id}"
    )

    return message_id


def publish_ingestion_requested(job_id, source_id):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_INGESTION_REQUESTED,
        payload
    )

def publish_job_completed(job_id, source_id):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_JOB_COMPLETED,
        payload
    )


def publish_job_failed(job_id, source_id, error_message):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "error_message": error_message
    }

    return publish_event(
        settings.PUBSUB_TOPIC_JOB_FAILED,
        payload
    )