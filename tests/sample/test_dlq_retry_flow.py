import sys
import os
import json
import time
import uuid
import types
import socket
import pytest
from unittest.mock import MagicMock
from google.cloud import pubsub_v1
from google.api_core.exceptions import AlreadyExists

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock SessionLocal before importing settings/models that might initialize connections
class MockJob:
    # Use class variables so state persists across DB session reinstantiations
    retry_count = 0
    status = "RECEIVED"
    error_message = None

    def __init__(self):
        self.job_id = None
        self.source_id = "11eb34f7-e438-4bfa-8f4b-325bdfa4a753"

class MockSession:
    def __init__(self):
        self.job = MockJob()

    def rollback(self):
        pass

    def get(self, model_class, ident):
        self.job.job_id = ident
        return self.job

    def commit(self):
        pass

    def close(self):
        pass

# Create dummy modules to override app.db.database without triggering connection
db_module = types.ModuleType('app.db.database')
db_module.SessionLocal = MagicMock(return_value=MockSession())
sys.modules['app.db.database'] = db_module

# Also mock app.db.session just in case
session_module = types.ModuleType('app.db.session')
session_module.get_db = MagicMock()
sys.modules['app.db.session'] = session_module

# Mock workers.inference.processor.infer_target_landing_zone to raise transient socket timeout
async def mock_infer_target_landing_zone(job_id, artifact_id, metadata_profile_id, db):
    raise socket.timeout("Transient socket timeout simulated")

# Apply the mock to processor before importing subscriber
import workers.inference.processor
workers.inference.processor.infer_target_landing_zone = mock_infer_target_landing_zone

# Patch retry handler's get_retry_delay to return 0.1s delay so test runs fast
import workers.common.retry_handler
workers.common.retry_handler.get_retry_delay = MagicMock(return_value=(0.1, "0.1s (mocked short delay)"))

from app.core.settings import settings
from app.pubsub.publisher import publish_event

# Import subscriber AFTER patching processor
from workers.inference.subscriber import callback_metadata_vectorized

def setup_pubsub():
    publisher_client = pubsub_v1.PublisherClient()
    subscriber_client = pubsub_v1.SubscriberClient()

    # 1. Target Vectorized
    topic_v_path = publisher_client.topic_path(settings.GCP_PROJECT_ID, settings.PUBSUB_TOPIC_METADATA_VECTORIZED)
    try:
        publisher_client.create_topic(name=topic_v_path)
    except AlreadyExists:
        pass

    sub_v_path = subscriber_client.subscription_path(settings.GCP_PROJECT_ID, settings.PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED)
    try:
        subscriber_client.create_subscription(name=sub_v_path, topic=topic_v_path)
    except AlreadyExists:
        pass

    # 2. DLQ
    topic_dlq_path = publisher_client.topic_path(settings.GCP_PROJECT_ID, settings.PUBSUB_TOPIC_DEAD_LETTER)
    try:
        publisher_client.create_topic(name=topic_dlq_path)
    except AlreadyExists:
        pass

    sub_dlq_path = subscriber_client.subscription_path(settings.GCP_PROJECT_ID, settings.PUBSUB_SUBSCRIPTION_DEAD_LETTER)
    try:
        subscriber_client.create_subscription(name=sub_dlq_path, topic=topic_dlq_path)
    except AlreadyExists:
        pass

def test_dlq_retry_integration():
    setup_pubsub()

    # Reset MockJob state for the test
    MockJob.retry_count = 0
    MockJob.status = "RECEIVED"
    MockJob.error_message = None

    dlq_messages = []

    def dlq_callback(message):
        try:
            data = json.loads(message.data.decode("utf-8"))
            dlq_messages.append(data)
        finally:
            message.ack()

    # Subscribe to DLQ and worker topic
    subscriber_client = pubsub_v1.SubscriberClient()
    sub_dlq_path = subscriber_client.subscription_path(settings.GCP_PROJECT_ID, settings.PUBSUB_SUBSCRIPTION_DEAD_LETTER)
    dlq_future = subscriber_client.subscribe(sub_dlq_path, callback=dlq_callback)

    sub_v_path = subscriber_client.subscription_path(settings.GCP_PROJECT_ID, settings.PUBSUB_SUBSCRIPTION_METADATA_VECTORIZED)
    worker_future = subscriber_client.subscribe(sub_v_path, callback=callback_metadata_vectorized)

    # Publish message to trigger transient socket timeout
    job_uuid = uuid.uuid4()
    payload = {
        "job_id": str(job_uuid),
        "artifact_id": str(uuid.uuid4()),
        "metadata_profile_id": str(uuid.uuid4())
    }

    publish_event(settings.PUBSUB_TOPIC_METADATA_VECTORIZED, payload)

    # Wait for processing to complete and message to land in DLQ (max 8 seconds)
    start_time = time.time()
    while len(dlq_messages) == 0 and (time.time() - start_time) < 8.0:
        time.sleep(0.5)

    dlq_future.cancel()
    worker_future.cancel()

    assert len(dlq_messages) == 1
    dlq_payload = dlq_messages[0]
    assert dlq_payload["job_id"] == str(job_uuid)
    assert dlq_payload["attempt_number"] == 3
    assert dlq_payload["reason_type"] == "max retries exceeded"
    assert "Transient socket timeout simulated" in dlq_payload["error_message"]
