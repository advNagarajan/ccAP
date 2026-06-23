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
from app.models.db.user import User

from app.constants.job_status import JobStatus

from app.schemas.job import JobResponse
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_ingestion_requested
from app.api.dependencies import get_current_user
from app.services.audit_service import create_audit_entry

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

    # Create audit log entry
    create_audit_entry(
        db=db,
        user_email=current_user.email,
        action="Retry Job",
        details={"job_id": str(job_id), "new_job_id": str(new_job.job_id)}
    )

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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

    # Create audit log entry
    create_audit_entry(
        db=db,
        user_email=current_user.email,
        action="Kill Job",
        details={"job_id": str(job_id)}
    )

    return job


@router.get(
    "/jobs/{job_id}/details"
)
def get_job_details(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    from app.models.db.landing_inference import LandingInference
    from app.models.db.schema_validation import SchemaValidation
    from app.models.db.schema_drift import SchemaDrift
    from app.models.db.schema_recommendation import SchemaRecommendation
    from app.models.db.metadata_profile import MetadataProfile
    from app.models.db.target_catalog import TargetCatalog

    # 1. Fetch the Job
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # 2. Fetch associated details (since they may or may not exist yet, we fetch them safely)
    inference = db.execute(
        select(LandingInference).where(LandingInference.job_id == job_id)
    ).scalar_one_or_none()

    validation = db.execute(
        select(SchemaValidation).where(SchemaValidation.job_id == job_id)
    ).scalar_one_or_none()

    drift = db.execute(
        select(SchemaDrift).where(SchemaDrift.job_id == job_id)
    ).scalar_one_or_none()

    recommendation = db.execute(
        select(SchemaRecommendation).where(SchemaRecommendation.job_id == job_id)
    ).scalar_one_or_none()

    metadata_profile = db.execute(
        select(MetadataProfile).where(MetadataProfile.job_id == job_id)
    ).scalar_one_or_none()

    # 3. Fetch associated artifact records
    artifacts = db.execute(
        select(ArtifactRecord).where(ArtifactRecord.source_id == job.source_id)
    ).scalars().all()

    # 4. Determine target schema
    target_id = None
    if recommendation and recommendation.target_id:
        target_id = recommendation.target_id
    elif drift and drift.target_id:
        target_id = drift.target_id
    elif validation and validation.target_id:
        target_id = validation.target_id
    elif inference and inference.target_id:
        target_id = inference.target_id

    target = None
    if target_id:
        target = db.get(TargetCatalog, target_id)

    # 5. Construct unified response
    return {
        "job": {
            "job_id": job.job_id,
            "source_id": job.source_id,
            "status": job.status,
            "current_stage": job.current_stage,
            "retry_count": job.retry_count,
            "parent_job_id": job.parent_job_id,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "created_at": job.created_at,
            "updated_at": job.updated_at
        },
        "inference": {
            "confidence_score": float(inference.confidence_score) if inference else 0.0,
            "column_mapping": inference.column_mapping if inference else None,
            "unmapped_source_columns": inference.unmapped_source_columns if inference else None,
            "missing_target_columns": inference.missing_target_columns if inference else None,
            "reasoning": inference.reasoning if inference else None,
            "requires_review": inference.requires_review if inference else False
        } if inference else None,
        "validation": {
            "validation_status": validation.validation_status,
            "coverage_percentage": float(validation.coverage_percentage),
            "target_match_percentage": float(validation.target_match_percentage),
            "mapped_column_count": validation.mapped_column_count,
            "source_column_count": validation.source_column_count,
            "target_column_count": validation.target_column_count,
            "report_json": validation.report_json
        } if validation else None,
        "drift": {
            "drift_status": drift.drift_status,
            "drift_score": float(drift.drift_score),
            "drift_summary": drift.drift_summary
        } if drift else None,
        "recommendation": {
            "recommendation_status": recommendation.recommendation_status,
            "deterministic_findings": recommendation.deterministic_findings,
            "recommendations_list": recommendation.recommendations_list,
            "partitioning_recommendation": recommendation.partitioning_recommendation,
            "explanation": recommendation.explanation
        } if recommendation else None,
        "source_schema": metadata_profile.metadata_json if metadata_profile else None,
        "target_schema": target.schema_definition if target else None,
        "artifacts": [
            {
                "artifact_id": str(art.artifact_id),
                "source_id": str(art.source_id),
                "external_artifact_id": art.external_artifact_id,
                "artifact_name": art.artifact_name,
                "status": art.status,
                "processed_at": art.processed_at.isoformat() if art.processed_at else None,
                "discovered_at": art.discovered_at.isoformat() if art.discovered_at else None,
                "failure_reason": art.failure_reason,
                "artifact_metadata": art.artifact_metadata
            }
            for art in artifacts
        ]
    }


@router.get(
    "/jobs/{job_id}/stages"
)
def get_job_stages(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    from app.models.db.job_stage_history import JobStageHistory
    
    stmt = select(JobStageHistory).where(JobStageHistory.job_id == job_id).order_by(JobStageHistory.started_at.asc())
    result = db.execute(stmt)
    return result.scalars().all()