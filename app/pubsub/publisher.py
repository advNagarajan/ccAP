import functools
import json
import logging

from app.core.settings import settings

logger = logging.getLogger("publisher")

_sns_client = None
_topic_arn_cache = {}


def get_sns_client():
    global _sns_client
    if _sns_client is None:
        import boto3
        kwargs = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        _sns_client = boto3.client("sns", **kwargs)
    return _sns_client


def get_sns_topic_arn(sns_client, topic_name: str) -> str:
    if topic_name in _topic_arn_cache:
        return _topic_arn_cache[topic_name]
    res = sns_client.create_topic(Name=topic_name)
    arn = res["TopicArn"]
    _topic_arn_cache[topic_name] = arn
    return arn


def publish_event_aws(topic_name: str, payload: dict) -> str:
    sns = get_sns_client()
    topic_arn = get_sns_topic_arn(sns, topic_name)
    response = sns.publish(
        TopicArn=topic_arn,
        Message=json.dumps(payload)
    )
    msg_id = response.get("MessageId", "")
    print(f"Published to AWS SNS topic '{topic_name}' message_id={msg_id}")
    return msg_id


@functools.lru_cache(maxsize=1)
def get_publisher():
    from google.cloud import pubsub_v1
    return pubsub_v1.PublisherClient()


def publish_event(topic_name: str, payload: dict):
    if settings.CLOUD_PROVIDER.lower() == "aws":
        return publish_event_aws(topic_name, payload)


    pub = get_publisher()
    topic_path = pub.topic_path(
        settings.GCP_PROJECT_ID,
        topic_name
    )

    future = pub.publish(
        topic_path,
        json.dumps(payload).encode("utf-8")
    )

    message_id = future.result()

    print(
        f"Published {topic_name} "
        f"message_id={message_id}"
    )

    return message_id



def publish_ingestion_requested(job_id, source_id, force_dq: bool = False):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "force_dq": force_dq
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

def publish_quality_check_requested(
    job_id,
    parent_job_id,
    source_id,
    artifact_id
):
    payload = {
        "job_id": str(job_id),
        "parent_job_id": str(parent_job_id),
        "source_id": str(source_id),
        "artifact_id": str(artifact_id)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_QUALITY_CHECK_REQUESTED,
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

def publish_job_completed(
    job_id,
    source_id,
    recommendations_count: int = 0,
    target_name: str | None = None,
    artifact_id: str | None = None
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "recommendations_count": recommendations_count,
        "target_name": target_name
    }
    if artifact_id:
        payload["artifact_id"] = str(artifact_id)

    return publish_event(
        settings.PUBSUB_TOPIC_JOB_COMPLETED,
        payload
    )


def publish_job_failed(
    job_id,
    source_id,
    error_message,
    failed_at_worker=None,
    attempt_number=None,
    artifact_id: str | None = None
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "error_message": error_message
    }
    if failed_at_worker:
        payload["failed_at_worker"] = str(failed_at_worker)
    if attempt_number is not None:
        payload["attempt_number"] = int(attempt_number)
    if artifact_id:
        payload["artifact_id"] = str(artifact_id)

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


def publish_drift_detected(
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
        settings.PUBSUB_TOPIC_DRIFT_DETECTED,
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


def publish_fallback_requested(
    job_id,
    source_id,
    request_id,
    request_reason
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "request_id": str(request_id),
        "request_reason": str(request_reason)
    }

    return publish_event(
        settings.PUBSUB_TOPIC_FALLBACK_REQUESTED,
        payload
    )


def publish_quality_check_completed(
    job_id,
    source_id,
    artifact_id,
    status: str,
    rules_executed: int,
    rules_failed: int
):
    payload = {
        "job_id": str(job_id),
        "source_id": str(source_id),
        "artifact_id": str(artifact_id),
        "status": status,
        "rules_executed": rules_executed,
        "rules_failed": rules_failed
    }

    return publish_event(
        settings.PUBSUB_TOPIC_QUALITY_CHECK_COMPLETED,
        payload
    )