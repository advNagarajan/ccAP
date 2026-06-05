import json
import time
from datetime import datetime, UTC
from uuid import UUID

from app.db.database import SessionLocal
from app.models.job import Job
from app.constants.job_status import JobStatus
from app.pubsub.publisher import (
    publish_job_completed,
    publish_job_failed
)


def process_ingestion_requested(message_data: bytes):
    payload = json.loads(message_data.decode("utf-8"))

    job_id = UUID(payload["job_id"])

    db = SessionLocal()

    try:
        job = db.get(Job, job_id)

        if job is None:
            print(f"Job {job_id} not found")
            return

        print(f"Processing job {job_id}")

        job.status = JobStatus.RUNNING
        job.current_stage = "Worker Processing"
        job.started_at = datetime.now(UTC)

        db.commit()

        time.sleep(5)

        job.status = JobStatus.COMPLETED
        job.current_stage = "Completed"
        job.completed_at = datetime.now(UTC)

        db.commit()

        publish_job_completed(
            job.job_id,
            job.source_id
        )

        print(f"Completed job {job_id}")

    except Exception as e:
        print(f"Failed job {job_id}: {e}")

        try:
            job = db.get(Job, job_id)

            if job is not None:
                job.status = JobStatus.FAILED
                job.current_stage = "Failed"
                job.error_message = str(e)

                db.commit()

                publish_job_failed(
                    job.job_id,
                    job.source_id,
                    str(e)
                )

        except Exception:
            pass

    finally:
        db.close()