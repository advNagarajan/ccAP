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

def publish_dataset_received(
    job_id,
    source_id,
    artifact_external_id
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "artifact_external_id": artifact_external_id
    }

    return publish_event(
        settings.PUBSUB_TOPIC_DATASET_RECEIVED,
        payload
    )

def publish_metadata_extracted(
    job_id,
    artifact_id,
    metadata_profile_id
):

    payload = {
        "job_id": str(job_id),
        "artifact_id": str(artifact_id),
        "metadata_profile_id": str(
            metadata_profile_id
        )
    }

    return publish_event(
        settings.PUBSUB_TOPIC_METADATA_EXTRACTED,
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


def publish_target_mutated(target_id):
    payload = {
        "target_id": str(target_id)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_TARGET_MUTATED,
        payload
    )


def publish_feedback_submitted(job_id, target_id, user_action, notes):
    payload = {
        "job_id": str(job_id),
        "target_id": str(target_id),
        "user_action": user_action,
        "notes": notes
    }

    return publish_event(
        settings.PUBSUB_TOPIC_FEEDBACK_SUBMITTED,
        payload
    )


def publish_metadata_vectorized(
    job_id,
    artifact_id,
    metadata_profile_id
):
    payload = {
        "job_id": str(job_id),
        "artifact_id": str(artifact_id),
        "metadata_profile_id": str(
            metadata_profile_id
        )
    }

    return publish_event(
        settings.PUBSUB_TOPIC_METADATA_VECTORIZED,
        payload
    )


def publish_target_inferred(
    job_id,
    artifact_id,
    metadata_profile_id,
    inference_id,
    target_id,
    confidence_score,
    requires_review
):
    payload = {
        "job_id": str(job_id),
        "artifact_id": str(artifact_id),
        "metadata_profile_id": str(metadata_profile_id),
        "inference_id": str(inference_id),
        "target_id": str(target_id) if target_id else None,
        "confidence_score": float(confidence_score),
        "requires_review": bool(requires_review)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_TARGET_INFERRED,
        payload
    )


def publish_schema_validated(
    job_id,
    artifact_id,
    inference_id,
    validation_id,
    validation_status
):
    payload = {
        "job_id": str(job_id),
        "artifact_id": str(artifact_id),
        "inference_id": str(inference_id),
        "validation_id": str(validation_id),
        "validation_status": str(validation_status)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_SCHEMA_VALIDATED,
        payload
    )


def publish_schema_drifted(
    job_id,
    artifact_id,
    drift_id,
    drift_status,
    drift_score
):
    payload = {
        "job_id": str(job_id),
        "artifact_id": str(artifact_id),
        "drift_id": str(drift_id),
        "drift_status": str(drift_status),
        "drift_score": float(drift_score)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_SCHEMA_DRIFTED,
        payload
    )


def publish_fallback_landing_created(
    job_id,
    source_id,
    backup_table_name
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "backup_table_name": str(backup_table_name)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_FALLBACK_LANDING_CREATED,
        payload
    )