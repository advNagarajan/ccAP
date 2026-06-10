from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job_stage_history import JobStageHistory


def start_stage(job_id, stage_name, db: Session, details=None):

    record = JobStageHistory(
        job_id=job_id,
        stage_name=stage_name,
        status="RUNNING",
        started_at=datetime.now(UTC),
        details=details
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def complete_stage(stage_history_id, db: Session, details=None):

    record = db.get(JobStageHistory, stage_history_id)

    if record is None:
        return

    record.status = "COMPLETED"
    record.completed_at = datetime.now(UTC)

    if details is not None:
        record.details = details

    db.commit()


def fail_stage(stage_history_id, reason, db: Session):

    import traceback

    record = db.get(JobStageHistory, stage_history_id)

    if record is None:
        return

    record.status = "FAILED"
    record.completed_at = datetime.now(UTC)

    existing_details = record.details or {}
    existing_details["error"] = str(reason)
    existing_details["traceback"] = traceback.format_exc()

    record.details = existing_details

    db.commit()


def get_running_stage(job_id, stage_name, db: Session):

    return db.execute(
        select(JobStageHistory).where(
            JobStageHistory.job_id == job_id,
            JobStageHistory.stage_name == stage_name,
            JobStageHistory.status == "RUNNING"
        )
    ).scalar_one_or_none()