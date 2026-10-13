import json
import logging
import time
from typing import Callable
from azure.servicebus import ServiceBusClient, ServiceBusReceivedMessage

from app.core.settings import settings

logger = logging.getLogger("azure_subscriber")


class AzureMessageWrapper:
    """
    Wraps Azure ServiceBusReceivedMessage to match Google Pub/Sub message interface.
    Provides `.data`, `.message_id`, `.delivery_attempt`, `.ack()`, and `.nack()`
    so existing worker callbacks, failure handlers, and retry pipelines work seamlessly.
    """

    def __init__(self, raw_message: ServiceBusReceivedMessage, receiver):
        self._raw = raw_message
        self._receiver = receiver

        # Azure ServiceBus body can be bytes or iterable of bytes
        body_parts = list(raw_message.body)
        if body_parts and isinstance(body_parts[0], bytes):
            self.data = b"".join(body_parts)
        elif body_parts and isinstance(body_parts[0], str):
            self.data = "".join(body_parts).encode("utf-8")
        else:
            self.data = str(raw_message).encode("utf-8")

        self.message_id = str(raw_message.message_id or raw_message.sequence_number)
        self.delivery_attempt = raw_message.delivery_count or 1
        self.attributes = dict(raw_message.application_properties or {})

    def ack(self):
        """Acknowledge and remove message from the subscription queue."""
        try:
            self._receiver.complete_message(self._raw)
        except Exception as e:
            logger.error(f"Failed to ack/complete Azure message {self.message_id}: {e}")

    def nack(self):
        """Abandon message so it can be re-delivered (or dead-lettered after max attempts)."""
        try:
            self._receiver.abandon_message(self._raw)
        except Exception as e:
            logger.error(f"Failed to nack/abandon Azure message {self.message_id}: {e}")


def start_azure_subscriber(
    topic_name: str,
    subscription_name: str,
    callback_fn: Callable
) -> None:
    """
    Continuously polls the specified Azure Service Bus topic subscription and dispatches
    incoming messages through the provided callback function.
    """
    conn_str = settings.AZURE_SERVICEBUS_CONNECTION_STRING
    if not conn_str:
        raise ValueError(
            "AZURE_SERVICEBUS_CONNECTION_STRING is required to run worker in Azure mode."
        )

    logger.info(
        f"Starting Azure Service Bus subscriber for topic='{topic_name}' "
        f"subscription='{subscription_name}'..."
    )

    while True:
        try:
            with ServiceBusClient.from_connection_string(conn_str) as client:
                with client.get_subscription_receiver(
                    topic_name=topic_name,
                    subscription_name=subscription_name,
                    max_wait_time=5
                ) as receiver:
                    logger.info(
                        f"Connected to Azure Service Bus: {topic_name}/{subscription_name}"
                    )
                    while True:
                        messages = receiver.receive_messages(
                            max_message_count=1,
                            max_wait_time=5
                        )
                        for msg in messages:
                            wrapped_msg = AzureMessageWrapper(msg, receiver)
                            callback_fn(wrapped_msg)
        except KeyboardInterrupt:
            logger.info("Azure subscriber loop terminated by user.")
            break
        except Exception as e:
            logger.error(
                f"Azure Service Bus subscriber encountered error on '{subscription_name}': {e}. "
                f"Reconnecting in 10 seconds...",
                exc_info=True
            )
            time.sleep(10)


def start_azure_multi_subscriber(
    subscriptions_map: dict[str, str],
    make_callback_fn: Callable
) -> None:
    """
    Spawns background listener threads for multiple Azure Service Bus topic subscriptions.
    Used by router workers like worker-notification.
    """
    import threading

    logger.info(f"Starting multi-subscription listener for {len(subscriptions_map)} Azure topics...")
    threads = []
    for topic_name, sub_name in subscriptions_map.items():
        if not sub_name:
            continue
        cb = make_callback_fn(topic_name)
        t = threading.Thread(
            target=start_azure_subscriber,
            args=(topic_name, sub_name, cb),
            daemon=True
        )
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Multi-subscription listener stopped by user.")

