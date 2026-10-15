import json
import logging
import time
from typing import Callable

from app.core.settings import settings

logger = logging.getLogger("aws_subscriber")


class AWSMessageWrapper:
    """
    Wraps an Amazon SQS message to match the Google Pub/Sub message interface.
    Provides `.data`, `.message_id`, `.delivery_attempt`, `.ack()`, and `.nack()`
    so worker callbacks, retry handlers, and failure processors work seamlessly.
    """

    def __init__(self, raw_sqs_message: dict, sqs_client, queue_url: str):
        self._raw = raw_sqs_message
        self._sqs = sqs_client
        self._queue_url = queue_url

        body_str = raw_sqs_message.get("Body", "")

        # Handle SNS-to-SQS envelope
        try:
            parsed = json.loads(body_str)
            if isinstance(parsed, dict) and "Message" in parsed and "TopicArn" in parsed:
                # SNS forwarded payload
                inner_message = parsed["Message"]
                self.data = inner_message.encode("utf-8") if isinstance(inner_message, str) else json.dumps(inner_message).encode("utf-8")
            else:
                self.data = body_str.encode("utf-8")
        except Exception:
            self.data = body_str.encode("utf-8")

        self.message_id = raw_sqs_message.get("MessageId", "")
        self.receipt_handle = raw_sqs_message.get("ReceiptHandle", "")

        # Read delivery attempt from SQS attributes
        attrs = raw_sqs_message.get("Attributes", {})
        try:
            self.delivery_attempt = int(attrs.get("ApproximateReceiveCount", 1))
        except (ValueError, TypeError):
            self.delivery_attempt = 1

        self.attributes = dict(raw_sqs_message.get("MessageAttributes", {}))

    def ack(self):
        """Acknowledge and delete message from the SQS queue."""
        try:
            self._sqs.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=self.receipt_handle
            )
        except Exception as e:
            logger.error(f"Failed to ack/delete SQS message {self.message_id}: {e}")

    def nack(self):
        """Release message back to SQS immediately (set VisibilityTimeout to 0)."""
        try:
            self._sqs.change_message_visibility(
                QueueUrl=self._queue_url,
                ReceiptHandle=self.receipt_handle,
                VisibilityTimeout=0
            )
        except Exception as e:
            logger.error(f"Failed to nack/release SQS message {self.message_id}: {e}")


def get_sqs_client():
    import boto3
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("sqs", **kwargs)


def get_queue_url(sqs_client, queue_name: str) -> str:
    """Gets the SQS QueueUrl (or creates queue if it does not exist in dev)."""
    try:
        res = sqs_client.get_queue_url(QueueName=queue_name)
        return res["QueueUrl"]
    except Exception:
        # Create queue dynamically if not found
        res = sqs_client.create_queue(QueueName=queue_name)
        return res["QueueUrl"]


def start_aws_subscriber(
    topic_name: str,
    subscription_name: str,
    callback_fn: Callable
) -> None:
    """
    Continuously long-polls an AWS SQS queue (subscribed to the topic) and dispatches
    incoming messages to the callback.
    """
    sqs = get_sqs_client()
    queue_name = subscription_name.replace("_", "-")
    queue_url = get_queue_url(sqs, queue_name)

    logger.info(
        f"Starting AWS SQS subscriber for queue='{queue_name}' "
        f"(topic='{topic_name}')..."
    )

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10, # Long polling
                AttributeNames=["All"],
                MessageAttributeNames=["All"]
            )

            messages = response.get("Messages", [])
            for msg in messages:
                wrapped_msg = AWSMessageWrapper(msg, sqs, queue_url)
                callback_fn(wrapped_msg)

        except KeyboardInterrupt:
            logger.info("AWS SQS subscriber stopped by user.")
            break
        except Exception as e:
            logger.error(
                f"AWS SQS subscriber error on '{queue_name}': {e}. Reconnecting in 5s...",
                exc_info=True
            )
            time.sleep(5)


def start_aws_multi_subscriber(
    subscriptions_map: dict[str, str],
    make_callback_fn: Callable
) -> None:
    """
    Spawns background polling threads for multiple SQS queues (used by worker-notification).
    """
    import threading

    logger.info(f"Starting multi-queue listener for {len(subscriptions_map)} SQS queues...")
    threads = []
    for topic_name, sub_name in subscriptions_map.items():
        if not sub_name:
            continue
        cb = make_callback_fn(topic_name)
        t = threading.Thread(
            target=start_aws_subscriber,
            args=(topic_name, sub_name, cb),
            daemon=True
        )
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Multi-queue listener stopped by user.")
