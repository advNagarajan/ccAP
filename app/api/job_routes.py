from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.db.job import Job
from app.models.db.artifact_record import ArtifactRecord

from app.constants.job_status import JobStatus

from app.schemas.job import JobResponse
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_ingestion_requested

router = APIRouter(tags=["Jobs"])

VALID_JOB_STATUSES = {
    JobStatus.RECEIVED,
    JobStatus.VALIDATING,
    JobStatus.RUNNING,
    JobStatus.COMPLETED,
    JobStatus.FAILED,
    JobStatus.CANCELLED,
    JobStatus.RETRIED
}

@router.get(
    "/jobs",
    response_model=list[JobResponse]
)
def get_jobs(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    stmt = select(Job)

    if status:

        status = status.upper()

        if status not in VALID_JOB_STATUSES:
            raise HTTPException(
                status_code=400,
                detail="Invalid status filter"
            )

        stmt = stmt.where(
            Job.status == status
        )

    result = db.execute(stmt)

    return result.scalars().all()


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse
)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    job = db.get(
        Job,
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return job


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=201
)
def retry_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    # 1. Fetch the failed job
    old_job = db.get(Job, job_id)
    if old_job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # 2. Check if the job's status is FAILED
    if old_job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Only failed jobs can be retried. Current status is {old_job.status}"
        )

    # 3. Traversal lineage to check max retries <= 2
    retry_count = 0
    curr_job = old_job
    while curr_job.parent_job_id is not None:
        retry_count += 1
        curr_job = db.get(Job, curr_job.parent_job_id)
        if not curr_job:
            break

    if retry_count >= 2:
        raise HTTPException(
            status_code=400,
            detail="Maximum retry limit (2) reached for this job lineage."
        )

    # 4. Reset ArtifactRecords for the source to allow GCS re-ingestion
    db.execute(
        update(ArtifactRecord)
        .where(ArtifactRecord.source_id == old_job.source_id)
        .values(
            status="DISCOVERED",
            processed_at=None,
            failure_reason=None
        )
    )

    # 5. Create the new job & update old job status to RETRIED
    old_job.status = JobStatus.RETRIED
    new_job = Job(
        source_id=old_job.source_id,
        status=JobStatus.RECEIVED,
        parent_job_id=old_job.job_id
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # 6. Trigger the ingestion pipeline (dataset acquisition stage)
    stage = start_stage(new_job.job_id, "Ingestion Trigger", db)
    try:
        publish_ingestion_requested(
            new_job.job_id,
            new_job.source_id
        )
        complete_stage(stage.stage_history_id, db)
    except Exception as e:
        fail_stage(stage.stage_history_id, e, db)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish retry request: {e}"
        )

    return new_job


@router.post(
    "/jobs/{job_id}/kill",
    response_model=JobResponse,
    status_code=200
)
def kill_job(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    # 1. Fetch the job
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # 2. Only allow killing active or failed jobs
    if job.status not in (JobStatus.RUNNING, JobStatus.FAILED, JobStatus.RECEIVED, JobStatus.VALIDATING):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot kill a job with status {job.status}"
        )

    # 3. Update status to CANCELLED
    job.status = JobStatus.CANCELLED
    job.error_message = "Job manually terminated/killed by user."
    
    # 4. Cleanup any pending schema fallback requests
    from app.models.db.schema_fallback_request import SchemaFallbackRequest
    db.execute(
        update(SchemaFallbackRequest)
        .where(
            SchemaFallbackRequest.job_id == job_id,
            SchemaFallbackRequest.request_status == "PENDING"
        )
        .values(request_status="CANCELLED")
    )
    
    db.commit()
    db.refresh(job)
    return job