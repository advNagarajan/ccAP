import logging
import threading
import time
import socket
import json
from sqlalchemy.orm import Session
from app.models.db.job import Job
from app.constants.job_status import JobStatus
from app.pubsub.publisher import publish_job_failed, publish_event
from app.core.settings import settings

# Option C: Import Google Cloud core exceptions
from google.api_core import exceptions as google_exceptions
import requests
import urllib3
try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger("retry_handler")

def is_transient_error(e: Exception) -> bool:
    """
    Classifies if the exception is retryable (transient) using Option C.
    Identifies:
    - Google Core API Exceptions (ResourceExhausted [429], ServiceUnavailable [503], 
      DeadlineExhausted [504], Aborted [409], InternalServerError [500])
    - Database connectivity issues (SQLAlchemy OperationalError, DBAPIError connection timeouts/drops)
    - Network/connection timeouts (socket.timeout, urllib3 connection/timeout, requests connection/timeout, httpx connect/timeout)
    - Python built-in TimeoutError
    - Excludes permanent errors (InvalidArgument, NotFound, PermissionDenied, IntegrityError, syntax/code bugs)
    """
    # 1. Exclude standard code/logic errors (always permanent)
    if isinstance(e, (KeyError, IndexError, AttributeError, TypeError, ValueError, ZeroDivisionError, NotImplementedError)):
        return False

    # 2. Check Google API Exceptions
    if isinstance(e, google_exceptions.GoogleAPICallError):
        # 429: Rate Limits, 503: Unavailable, 504: Gateway Timeout, 409: Concurrent Aborted, 500: Internal Server Error
        if e.code in (429, 500, 503, 504, 409):
            return True
        # Check standard subclass types
        if isinstance(e, (google_exceptions.ResourceExhausted, 
                          google_exceptions.ServiceUnavailable, 
                          google_exceptions.DeadlineExceeded, 
                          google_exceptions.Aborted,
                          google_exceptions.InternalServerError)):
            return True
        # Explicitly permanent Google errors: 400 InvalidArgument, 404 NotFound, 403 PermissionDenied, 401 Unauthenticated
        if e.code in (400, 401, 403, 404):
            return False
        return False

    # 3. Check Database (SQLAlchemy / PostgreSQL) Operational Exceptions
    # If the database goes down or restarts temporarily, we want to retry.
    if isinstance(e, (sa_exceptions.OperationalError, sa_exceptions.DBAPIError) if 'sa_exceptions' in locals() else Exception):
        # Let's import sa_exceptions safely inside the check or globally
        from sqlalchemy import exc as sa_exceptions
        if isinstance(e, (sa_exceptions.OperationalError, sa_exceptions.DBAPIError)):
            # Exclude specific non-transient DB exceptions like IntegrityError (unique/foreign key violation)
            if isinstance(e, sa_exceptions.IntegrityError):
                return False
            # DataError (e.g. invalid string length, invalid value format)
            if isinstance(e, sa_exceptions.DataError):
                return False
            return True

    # 4. Check low-level socket connection/timeout errors
    if isinstance(e, (socket.timeout, TimeoutError)):
        return True
    
    # 5. Check requests library network exceptions
    if isinstance(e, (requests.exceptions.Timeout, 
                      requests.exceptions.ConnectionError)):
        return True
    # If requests.HTTPError, check status code
    if isinstance(e, requests.exceptions.HTTPError) and e.response is not None:
        if e.response.status_code in (429, 500, 502, 503, 504):
            return True
        return False

    # 6. Check urllib3 exceptions
    if isinstance(e, (urllib3.exceptions.TimeoutError,
                      urllib3.exceptions.ConnectionError,
                      urllib3.exceptions.HTTPError)):
        return True

    # 7. Check httpx exceptions (if installed)
    if httpx is not None and isinstance(e, httpx.HTTPError):
        if isinstance(e, (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError)):
            return True
        if hasattr(e, 'response') and e.response is not None:
            if e.response.status_code in (429, 500, 502, 503, 504):
                return True
        return False

    # 8. Check error messages for common cloud/infra keywords as a fallback
    err_str = str(e).lower()
    if any(keyword in err_str for keyword in ["resource_exhausted", "rate limit", "quota", "503", "504", "timeout", "connection refused", "connection pool"]):
        return True

    return False

def is_network_infra_error(e: Exception) -> bool:
    """
    Identifies internet connection disconnects, DB connection timeouts, or Cloud Infrastructure outages.
    These warrant a longer retry delay window.
    """
    # 1. Database connection down
    from sqlalchemy import exc as sa_exceptions
    if isinstance(e, (sa_exceptions.OperationalError, sa_exceptions.DBAPIError)):
        if not isinstance(e, (sa_exceptions.IntegrityError, sa_exceptions.DataError)):
            return True

    # 2. Standard connection/DNS errors
    if isinstance(e, (requests.exceptions.ConnectionError, urllib3.exceptions.ConnectionError)):
        return True
    if isinstance(e, (socket.gaierror, ConnectionRefusedError, ConnectionResetError)):
        return True
    
    # 3. HTTPX connection errors
    if httpx is not None and isinstance(e, (httpx.ConnectError, httpx.NetworkError)):
        return True
    
    # 4. Google 503 Service Unavailable (backend down/unreachable)
    if isinstance(e, google_exceptions.ServiceUnavailable) or (hasattr(e, 'code') and e.code == 503):
        return True

    # 5. Common socket connection error messages
    err_str = str(e).lower()
    if any(phrase in err_str for phrase in ["name or service not known", "dns", "connection aborted", "503 service unavailable", "failed to establish a new connection", "database connection"]):
        return True

    return False

def reset_retry_count(job_id: str, db: Session):
    """Resets the retry counter upon successful transition to the next stage."""
    if not job_id:
        return
    job = db.get(Job, job_id)
    if job:
        job.retry_count = 0
        db.commit()

def delayed_nack_worker(message, delay_seconds: int, job_id: str, worker_name: str):
    """Sleeps inside a daemon background thread before calling nack to release the message."""
    logger.info(f"Background thread sleeping for {delay_seconds}s before nacking message for job={job_id}...")
    time.sleep(delay_seconds)
    try:
        # Inform Pub/Sub server to redeliver the message
        message.nack()
        logger.info(f"Nacked message {message.message_id} for job={job_id} successfully.")
    except Exception as nack_err:
        logger.error(f"Failed to nack message {message.message_id} in background thread: {nack_err}")

def get_retry_delay(e: Exception, attempt: int) -> tuple[int, str]:
    """
    Dynamically calculates retry delay based on the specific type of transient error:
    - Quota/Rate Limit (429/ResourceExhausted): 30s (1st retry), 90s (2nd retry)
    - Major Network/Outage (is_network_infra_error): 300s (1st retry), 1800s (2nd retry)
    - Timeout (socket.timeout/TimeoutError/DeadlineExceeded): 15s (1st retry), 45s (2nd retry)
    - Standard/Database Transient Errors: 10s (1st retry), 30s (2nd retry)
    """
    err_str = str(e).lower()
    is_rate_limit = False

    # Check for Google Quota / Rate limits
    if isinstance(e, google_exceptions.GoogleAPICallError) and e.code == 429:
        is_rate_limit = True
    elif isinstance(e, google_exceptions.ResourceExhausted):
        is_rate_limit = True
    elif isinstance(e, requests.exceptions.HTTPError) and e.response is not None and e.response.status_code == 429:
        is_rate_limit = True
    elif httpx is not None and isinstance(e, httpx.HTTPError) and hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
        is_rate_limit = True
    elif any(keyword in err_str for keyword in ["rate limit", "resource_exhausted", "quota limit", "too many requests"]):
        is_rate_limit = True

    if is_rate_limit:
        delay = 30 if attempt == 2 else 90
        return delay, f"{delay}s (rate limiting/quota exhaustion, waiting for bucket refill)"

    # Check for major infra issue
    if is_network_infra_error(e):
        delay = 300 if attempt == 2 else getattr(settings, "RETRY_DELAY_INFRA_ERROR", 1800)
        return delay, f"{delay}s (network offline/cloud database infrastructure downtime)"

    # Check for timeouts
    is_timeout = False
    if isinstance(e, (socket.timeout, TimeoutError, google_exceptions.DeadlineExceeded)):
        is_timeout = True
    elif isinstance(e, requests.exceptions.Timeout):
        is_timeout = True
    elif httpx is not None and isinstance(e, httpx.TimeoutException):
        is_timeout = True
    elif "timeout" in err_str or "deadline exceeded" in err_str:
        is_timeout = True

    if is_timeout:
        delay = 15 if attempt == 2 else 45
        return delay, f"{delay}s (request timeout/deadline exceeded)"

    # Default transient/database error
    delay = (
        getattr(settings, "RETRY_DELAY_TRANSIENT_ERROR_1", 10)
        if attempt == 2 else
        getattr(settings, "RETRY_DELAY_TRANSIENT_ERROR_2", 30)
    )
    return delay, f"{delay}s (general transient API/database anomaly)"

def handle_worker_failure(job_id: str, worker_name: str, error: Exception, message, db: Session):
    """
    Main orchestrator for managing worker execution failures:
    1. Determines attempt count via GCP attributes (Option A) or database fallback.
    2. Classifies if the exception is transient (Option C) and checks retry eligibility.
    3. Handles delayed retries (10s/30s/30m) via non-blocking daemon thread.
    4. For non-retryable or exhausted failures: updates DB status, forces a publish to
       the dead-letter topic manually, and ACKs the message to clear it.
    """
    # Rollback current processor database transaction to avoid dirty states
    db.rollback()

    if not job_id:
        logger.error(f"No job_id found in message payload. Acknowledging invalid message. Error: {error}")
        message.ack()
        return

    job = db.get(Job, job_id)
    if not job:
        logger.error(f"Job {job_id} not found in database. Acknowledging orphan message. Error: {error}")
        message.ack()
        return

    # Option A: Check GCP delivery_attempt attribute
    delivery_attempt_attr = message.attributes.get("delivery_attempt")
    if delivery_attempt_attr is not None:
        try:
            attempt = int(delivery_attempt_attr)
            logger.info(f"Option A: GCP Pub/Sub reported delivery_attempt={attempt} for job={job_id}")
            # Sync metadata to database
            job.retry_count = attempt - 1
            db.commit()
        except ValueError:
            # Fallback to DB if attribute is corrupted
            job.retry_count += 1
            db.commit()
            attempt = job.retry_count + 1
    else:
        # DB fallback (local development / emulator)
        attempt = job.retry_count + 1
        job.retry_count += 1
        db.commit()
        logger.info(f"Option A Fallback: DB reports retry attempt={attempt} for job={job_id}")

    is_transient = is_transient_error(error)

    # 2 retries max = 3 total attempts
    if is_transient and attempt <= 2:
        # Calculate delay dynamically based on failure type
        delay_seconds, delay_desc = get_retry_delay(error, attempt)

        logger.warning(
            f"Transient failure in worker '{worker_name}' for Job {job_id} (Attempt {attempt}/3). "
            f"Scheduling retry in {delay_desc}. Error: {error}"
        )

        job.error_message = f"Attempt {attempt} failed in '{worker_name}': {str(error)} (Retrying in {delay_desc})"
        db.commit()

        # Spin up background thread to perform non-blocking delayed nack
        t = threading.Thread(
            target=delayed_nack_worker, 
            args=(message, delay_seconds, job_id, worker_name), 
            daemon=True
        )
        t.start()

    else:
        # Non-transient error OR max retries (3 attempts) exceeded
        reason_desc = "max retries exceeded" if attempt >= 3 else "non-retryable permanent error"
        error_msg = f"Failed in worker '{worker_name}': {str(error)} ({reason_desc})"
        
        logger.error(f"Job {job_id} failed permanently in worker '{worker_name}' due to: {error_msg}")

        # Update Job status in DB
        job.status = JobStatus.FAILED
        job.error_message = error_msg
        db.commit()

        # Force a publish to the Dead Letter Topic manually so it is captured immediately
        try:
            # Get the original payload data
            original_payload = json.loads(message.data.decode("utf-8"))
            dlq_payload = {
                "job_id": job_id,
                "source_id": str(job.source_id),
                "failed_at_worker": worker_name,
                "attempt_number": attempt,
                "reason_type": reason_desc,
                "error_message": str(error),
                "original_payload": original_payload
            }
            # Manually publish to Dead Letter Topic using setting
            dlq_topic = getattr(settings, "PUBSUB_TOPIC_DEAD_LETTER", "job-failures-dead-letter-topic")
            publish_event(dlq_topic, dlq_payload)
            logger.info(f"Forced manual publish to '{dlq_topic}' for job={job_id}")
        except Exception as pub_dlq_err:
            logger.error(f"Failed to publish manually to DLQ topic for job={job_id}: {pub_dlq_err}")

        # Also publish standard job-failed event
        try:
            publish_job_failed(job.job_id, job.source_id, error_msg, failed_at_worker=worker_name, attempt_number=attempt)
        except Exception as pub_failed_err:
            logger.error(f"Failed to publish standard job failed event for job={job_id}: {pub_failed_err}")

        # ACK original message to remove it from Pub/Sub active queue
        message.ack()
        logger.info(f"Acknowledged permanently failed message {message.message_id} for job={job_id}.")
