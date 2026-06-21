import uuid
from unittest.mock import MagicMock
from app.services.notification.slack import SlackNotificationChannel
from app.core.settings import settings


def test_send_slack_channel_notifications():
    """
    Manual test function to verify end-to-end Slack webhook routing.
    Can be run via pytest: pytest -s tests/test_slack_channels.py
    """
    print("\nTesting Slack Notification Webhook Routing...")
    print(f"SLACK_WEBHOOK_DEAD_LETTER: {settings.SLACK_WEBHOOK_DEAD_LETTER}")
    print(f"SLACK_WEBHOOK_NEW_TABLE: {settings.SLACK_WEBHOOK_NEW_TABLE}")
    print(f"SLACK_WEBHOOK_URL (misc): {settings.SLACK_WEBHOOK_URL}")
    print(f"SLACK_WEBHOOK_JOB_COMPLETED: {settings.SLACK_WEBHOOK_JOB_COMPLETED}")
    print(f"SLACK_WEBHOOK_JOB_FAILED: {settings.SLACK_WEBHOOK_JOB_FAILED}")

    db = MagicMock()
    channel = SlackNotificationChannel()

    job_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())

    # 1. Job Completed
    print("\nSending 'job-completed' notification...")
    channel.send_message(
        subject="Success: Job Processing Completed Successfully",
        message=f"Job ID: {job_id}\nSource ID: {source_id}\nThe landing and inference job finished without errors.\nTarget Table: users_test\nRecommendations Generated: 5",
        db=db,
        details={"topic": "job-completed"}
    )

    # 2. Job Failed
    print("\nSending 'job-failed' notification...")
    channel.send_message(
        subject="Alert: Job Processing Failed",
        message=f"Job ID: {job_id}\nSource ID: {source_id}\nFailed Worker: validation_worker\nAttempt Number: 1\nError Details: Schema validation failed.",
        db=db,
        details={"topic": "job-failed"}
    )

    # 3. Dead Letter
    print("\nSending 'dead-letter' notification...")
    channel.send_message(
        subject="CRITICAL: Job Failed & Hit Dead Letter Queue",
        message=f"Job ID: {job_id}\nSource ID: {source_id}\nFailed Worker: drift_worker\nAttempt Number: 3\nError: Database connection timed out permanently.",
        db=db,
        details={"topic": "dead-letter"}
    )

    # 4. Fallback requested (New Table)
    print("\nSending 'fallback-requested' notification...")
    channel.send_message(
        subject="Action Required: Fallback Request Created",
        message=f"Job ID: {job_id}\nSource ID: {source_id}\nThreshold failure detected (CRITICAL_DRIFT). A fallback table proposal has been generated.\nPlease review and approve/reject fallback request ID: {uuid.uuid4()}",
        db=db,
        details={"topic": "fallback-requested"}
    )

    # 5. Fallback Default (Misc)
    print("\nSending 'unknown-topic' (misc) notification...")
    channel.send_message(
        subject="Info: System Maintenance Event",
        message="This is a test message to verify the default miscellaneous channel.",
        db=db,
        details={"topic": "misc-event"}
    )

    print("\nAll test notifications sent successfully!")
