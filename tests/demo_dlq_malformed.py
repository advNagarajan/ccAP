import os
import sys
import json
import uuid

# Ensure project root is in the Python search path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.settings import settings
from app.db.database import SessionLocal
from app.models.db.job import Job
from app.models.db.source import Source
from app.pubsub.publisher import publish_event


def main():
    db = SessionLocal()
    try:
        # Retrieve the latest job from the database to ensure the worker database check passes
        job = db.query(Job).order_by(Job.created_at.desc()).first()
        if job:
            job_id = job.job_id
            print(f"[+] Using latest Job ID from database: {job_id}")
        else:
            # Fallback: create a new job if none exists
            source = db.query(Source).first()
            if not source:
                print("[-] Error: No source found in the database. Please create a source first.")
                return
            new_job = Job(
                source_id=source.source_id,
                status="RECEIVED",
                current_stage="Metadata Vectorized"
            )
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            job_id = new_job.job_id
            print(f"[+] Created new Job in database: {job_id}")
    finally:
        db.close()

    # Build malformed payload: intentionally omit 'metadata_profile_id' to cause a KeyError in the worker
    payload = {
        "job_id": str(job_id),
        "artifact_id": str(uuid.uuid4())
    }

    print(f"[*] Publishing malformed message to topic '{settings.PUBSUB_TOPIC_METADATA_VECTORIZED}'...")
    print(f"    Payload: {json.dumps(payload)}")
    
    try:
        message_id = publish_event(settings.PUBSUB_TOPIC_METADATA_VECTORIZED, payload)
        print(f"[+] Published successfully! Message ID: {message_id}")
        print("[*] The worker will fail to process this message and route it to the Dead Letter Queue.")
    except Exception as e:
        print(f"[-] Failed to publish message: {e}")


if __name__ == "__main__":
    main()
