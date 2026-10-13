import logging
import time
from typing import Callable

from app.core.settings import settings

logger = logging.getLogger("worker_runner")


def run_worker_subscriber(
    topic_name: str,
    subscription_name: str,
    callback_fn: Callable,
    worker_name: str = "worker"
) -> None:
    """
    Unified subscriber entrypoint for all workers.
    Automatically routes to Azure Service Bus or Google Cloud Pub/Sub
    based on the `settings.CLOUD_PROVIDER` configuration toggle.
    """
    from workers.common.dummy_server import start_dummy_server
    start_dummy_server()

    is_azure = (
        settings.CLOUD_PROVIDER.lower() == "azure" or
        (bool(settings.AZURE_SERVICEBUS_CONNECTION_STRING) and settings.GCP_PROJECT_ID == "your-gcp-project-id")
    )

    if is_azure:
        from workers.common.azure_subscriber import start_azure_subscriber
        logger.info(f"[{worker_name}] Dispatching to Azure Service Bus mode...")
        start_azure_subscriber(
            topic_name=topic_name,
            subscription_name=subscription_name,
            callback_fn=callback_fn
        )
    else:
        from google.cloud import pubsub_v1
        logger.info(f"[{worker_name}] Dispatching to Google Cloud Pub/Sub mode...")
        while True:
            subscriber = None
            streaming_pull_future = None
            try:
                subscriber = pubsub_v1.SubscriberClient()
                subscription_path = subscriber.subscription_path(
                    settings.GCP_PROJECT_ID,
                    subscription_name
                )
                streaming_pull_future = subscriber.subscribe(
                    subscription_path,
                    callback=callback_fn
                )
                logger.info(f"[{worker_name}] Listening on GCP Pub/Sub: {subscription_path}")

                while streaming_pull_future.running():
                    time.sleep(1)

                if streaming_pull_future.done() and streaming_pull_future.exception():
                    streaming_pull_future.result()

            except KeyboardInterrupt:
                logger.info(f"[{worker_name}] Subscriber stopped by user.")
                if streaming_pull_future:
                    try:
                        streaming_pull_future.cancel()
                    except Exception:
                        pass
                if subscriber:
                    try:
                        subscriber.close()
                    except Exception:
                        pass
                break
            except Exception as e:
                logger.error(
                    f"[{worker_name}] Subscriber encountered error: {e}. Reconnecting in 10s...",
                    exc_info=True
                )
                if streaming_pull_future:
                    try:
                        streaming_pull_future.cancel()
                    except Exception:
                        pass
                if subscriber:
                    try:
                        subscriber.close()
                    except Exception:
                        pass
                time.sleep(10)
