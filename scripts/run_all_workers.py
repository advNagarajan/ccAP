"""
Continuous Background Worker Daemon Supervisor for AWS Data Landing Platform.

This supervisor starts and manages all 10 pipeline worker daemon subscribers concurrently:
1. Ingestion Worker (ingestion-requested-sub)
2. Metadata Extraction Worker (dataset-received-sub)
3. Metadata Vectorizer Worker (metadata-extracted-sub)
4. Semantic Inference Worker (metadata-vectorized-sub)
5. Schema Validation Worker (target-inferred-sub)
6. Schema Drift Worker (schema-validated-sub)
7. Drift Recommendation Worker (drift-detected-sub)
8. Data Quality Worker (quality-check-requested-sub)
9. Notification Worker (quality-check-completed, job-completed, job-failed -> Slack/Email)
10. Target Vectorizer Worker (target-mutated-sub, feedback-submitted-sub)

All workers continuously poll their Amazon SQS queues in non-blocking daemon threads.
"""
import os
import sys
import time
import signal
import threading
import logging

# Ensure project root is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
)
logger = logging.getLogger("worker_supervisor")

WORKER_DEFINITIONS = [
    ("Ingestion Worker", "workers.ingestion.subscriber", "start_subscriber"),
    ("Metadata Extraction", "workers.metadata.subscriber", "start_subscriber"),
    ("Metadata Vectorizer", "workers.vectorizers.metadata_vectorizer.subscriber", "start_subscriber"),
    ("Semantic Inference", "workers.inference.subscriber", "start_subscriber"),
    ("Schema Validation", "workers.validation.subscriber", "start_subscriber"),
    ("Schema Drift", "workers.drift.subscriber", "start_subscriber"),
    ("Recommendation", "workers.recommendation.subscriber", "start_subscriber"),
    ("Data Quality", "workers.quality.subscriber", "start_subscriber"),
    ("Notification Router (Slack/Email)", "workers.notification.subscriber", "start_subscriber"),
    ("Target Vectorizer", "workers.vectorizers.target_vectorizer.subscriber", "start_subscriber"),
]


def start_worker(name: str, module_path: str, func_name: str):
    logger.info(f"🚀 Starting {name} daemon...")
    try:
        mod = __import__(module_path, fromlist=[func_name])
        func = getattr(mod, func_name)
        func()
    except Exception as e:
        logger.error(f"❌ {name} encountered an error: {e}", exc_info=True)


def main():
    print("=" * 70)
    print("⚡ Smart Data Landing Platform: Continuous Worker Supervisor (AWS SQS)")
    print("=" * 70)

    threads = []
    for name, module_path, func_name in WORKER_DEFINITIONS:
        t = threading.Thread(
            target=start_worker,
            args=(name, module_path, func_name),
            name=name,
            daemon=True
        )
        t.start()
        threads.append(t)
        time.sleep(0.5)

    print("\n" + "=" * 70)
    print(f"✅ All {len(threads)} background workers are ACTIVE and listening on Amazon SQS!")
    print("   • Real-time Slack notifications are armed.")
    print("   • Ingestions triggered from UI or API will be processed automatically.")
    print("   • Press Ctrl+C to stop all worker daemons gracefully.")
    print("=" * 70 + "\n")

    def shutdown(signum, frame):
        logger.info("Received interrupt signal. Stopping worker supervisor...")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
