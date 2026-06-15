import socket
import json
import pytest
from unittest.mock import MagicMock, patch, ANY
import requests
import urllib3
from google.api_core import exceptions as google_exceptions
from sqlalchemy import exc as sa_exceptions

from app.constants.job_status import JobStatus
from app.models.job import Job
from workers.common.retry_handler import (
    is_transient_error,
    is_network_infra_error,
    reset_retry_count,
    handle_worker_failure
)

def test_is_transient_error():
    # Transient Google API Exceptions
    assert is_transient_error(google_exceptions.ResourceExhausted("Rate limit exceeded")) is True
    assert is_transient_error(google_exceptions.ServiceUnavailable("Service down")) is True
    assert is_transient_error(google_exceptions.DeadlineExceeded("Timeout")) is True
    assert is_transient_error(google_exceptions.Aborted("Conflict")) is True
    assert is_transient_error(google_exceptions.InternalServerError("Internal error")) is True

    # Permanent Google API Exceptions
    assert is_transient_error(google_exceptions.InvalidArgument("Bad payload")) is False
    assert is_transient_error(google_exceptions.NotFound("Resource not found")) is False
    assert is_transient_error(google_exceptions.PermissionDenied("No access")) is False

    # Standard python built-in code/logic errors (should not retry)
    assert is_transient_error(ValueError("Invalid value")) is False
    assert is_transient_error(KeyError("missing")) is False
    assert is_transient_error(TypeError("bad type")) is False

    # Low-level and requests network exceptions (transient)
    assert is_transient_error(socket.timeout("Socket timeout")) is True
    assert is_transient_error(TimeoutError("Timeout")) is True
    assert is_transient_error(requests.exceptions.Timeout("Request timeout")) is True
    assert is_transient_error(requests.exceptions.ConnectionError("Connection fail")) is True

    # Urllib3 transient exceptions
    assert is_transient_error(urllib3.exceptions.TimeoutError("urllib3 timeout")) is True

    # DB connectivity (transient)
    assert is_transient_error(sa_exceptions.OperationalError(None, None, "DB operational error")) is True
    
    # DB integrity violation (permanent)
    assert is_transient_error(sa_exceptions.IntegrityError(None, None, "Integrity constraint")) is False


def test_is_network_infra_error():
    # Socket name resolution and connect errors (outages)
    assert is_network_infra_error(socket.gaierror("Name or service not known")) is True
    assert is_network_infra_error(ConnectionRefusedError("Connection refused")) is True
    assert is_network_infra_error(ConnectionResetError("Connection reset")) is True

    # Google 503 Service Unavailable
    assert is_network_infra_error(google_exceptions.ServiceUnavailable("Google unavailable")) is True

    # DB Operational error
    assert is_network_infra_error(sa_exceptions.OperationalError(None, None, "operational error")) is True

    # Plain ValueError (not an infra error)
    assert is_network_infra_error(ValueError("Plain error")) is False


def test_reset_retry_count():
    db = MagicMock()
    job = MagicMock(spec=Job)
    job.retry_count = 3
    db.get.return_value = job

    reset_retry_count("some-job-id", db)

    db.get.assert_called_once_with(Job, "some-job-id")
    assert job.retry_count == 0
    db.commit.assert_called_once()


@patch("workers.common.retry_handler.threading.Thread")
@patch("workers.common.retry_handler.publish_event")
@patch("workers.common.retry_handler.publish_job_failed")
def test_handle_worker_failure_transient_first_retry(mock_pub_job_failed, mock_pub_event, mock_thread):
    # Setup
    db = MagicMock()
    job = MagicMock(spec=Job)
    job.retry_count = 0
    db.get.return_value = job

    # Mock pubsub message
    message = MagicMock()
    message.attributes = {"delivery_attempt": "2"}  # 2nd attempt = 1st retry
    message.data = b'{"payload_key": "payload_val"}'

    error = google_exceptions.ResourceExhausted("Rate limit exceeded")

    handle_worker_failure("some-job-id", "ingestion", error, message, db)

    # Asserts
    db.rollback.assert_called_once()
    assert job.retry_count == 1
    assert "Attempt 2 failed in 'ingestion'" in job.error_message
    db.commit.assert_called()

    # Verify background thread was started for nack
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()

    # No DLQ or fail events published for transient retry
    mock_pub_event.assert_not_called()
    mock_pub_job_failed.assert_not_called()
    message.ack.assert_not_called()


@patch("workers.common.retry_handler.threading.Thread")
@patch("workers.common.retry_handler.publish_event")
@patch("workers.common.retry_handler.publish_job_failed")
def test_handle_worker_failure_transient_exhausted(mock_pub_job_failed, mock_pub_event, mock_thread):
    # Setup
    db = MagicMock()
    job = MagicMock(spec=Job)
    job.retry_count = 2
    job.source_id = "source-uuid"
    job.job_id = "some-job-id"
    db.get.return_value = job

    # Mock pubsub message
    message = MagicMock()
    message.attributes = {"delivery_attempt": "4"}  # Attempt 4 = 3rd retry (exceeds limit of 2 retries)
    message.data = b'{"payload_key": "payload_val"}'

    error = google_exceptions.ResourceExhausted("Rate limit exceeded")

    handle_worker_failure("some-job-id", "ingestion", error, message, db)

    # Asserts
    db.rollback.assert_called_once()
    assert job.status == JobStatus.FAILED
    assert "Failed in worker 'ingestion'" in job.error_message
    assert "max retries exceeded" in job.error_message
    db.commit.assert_called()

    # Verify no nack thread started
    mock_thread.assert_not_called()

    # Verify manual publish to dead letter topic
    mock_pub_event.assert_called_once_with(
        "job-failures-dead-letter-topic",
        {
            "job_id": "some-job-id",
            "source_id": "source-uuid",
            "failed_at_worker": "ingestion",
            "attempt_number": 4,
            "reason_type": "max retries exceeded",
            "error_message": "429 Rate limit exceeded",
            "original_payload": {"payload_key": "payload_val"}
        }
    )

    # Verify publish standard job failed event
    mock_pub_job_failed.assert_called_once_with("some-job-id", "source-uuid", ANY)

    # Verify message is acknowledged to clear from Pub/Sub
    message.ack.assert_called_once()


@patch("workers.common.retry_handler.threading.Thread")
@patch("workers.common.retry_handler.publish_event")
@patch("workers.common.retry_handler.publish_job_failed")
def test_handle_worker_failure_permanent_error(mock_pub_job_failed, mock_pub_event, mock_thread):
    # Setup
    db = MagicMock()
    job = MagicMock(spec=Job)
    job.retry_count = 0
    job.source_id = "source-uuid"
    job.job_id = "some-job-id"
    db.get.return_value = job

    # Mock pubsub message
    message = MagicMock()
    message.attributes = {"delivery_attempt": "1"}
    message.data = b'{"payload_key": "payload_val"}'

    error = ValueError("Validation error - bad code")

    handle_worker_failure("some-job-id", "ingestion", error, message, db)

    # Asserts
    db.rollback.assert_called_once()
    assert job.status == JobStatus.FAILED
    assert "non-retryable permanent error" in job.error_message
    db.commit.assert_called()

    # Verify no nack thread started
    mock_thread.assert_not_called()

    # Verify DLQ manual publish
    mock_pub_event.assert_called_once_with(
        "job-failures-dead-letter-topic",
        {
            "job_id": "some-job-id",
            "source_id": "source-uuid",
            "failed_at_worker": "ingestion",
            "attempt_number": 1,
            "reason_type": "non-retryable permanent error",
            "error_message": "Validation error - bad code",
            "original_payload": {"payload_key": "payload_val"}
        }
    )

    # Verify publish standard job failed event
    mock_pub_job_failed.assert_called_once()

    # Verify message is acknowledged
    message.ack.assert_called_once()


@patch("workers.common.retry_handler.threading.Thread")
@patch("workers.common.retry_handler.publish_event")
@patch("workers.common.retry_handler.publish_job_failed")
def test_handle_worker_failure_no_gcp_attributes(mock_pub_job_failed, mock_pub_event, mock_thread):
    # Setup (fallback to DB retry count)
    db = MagicMock()
    job = MagicMock(spec=Job)
    job.retry_count = 0  # Initial attempt has retry_count = 0
    db.get.return_value = job

    # Mock pubsub message without delivery_attempt attribute
    message = MagicMock()
    message.attributes = {}
    message.data = b'{"payload_key": "payload_val"}'

    error = google_exceptions.ResourceExhausted("Rate limit exceeded")

    handle_worker_failure("some-job-id", "ingestion", error, message, db)

    # Asserts
    assert job.retry_count == 1  # Incremented via fallback
    db.commit.assert_called()

    # Verify background thread was started for nack
    mock_thread.assert_called_once()
    mock_thread.return_value.start.assert_called_once()
