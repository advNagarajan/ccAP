from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy import select, update, or_
from sqlalchemy.orm import Session

from app.db.session import get_db

from app.models.db.job import Job
from app.models.db.artifact_record import ArtifactRecord
from app.models.db.user import User
from app.models.db.job_stage_history import JobStageHistory

from app.constants.job_status import JobStatus

from app.schemas.job import JobResponse, JobDetailsResponse
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
    jobs = result.scalars().all()

    # Determine job types
    from app.models.db.data_quality_job import DataQualityJob
    quality_job_ids = set(
        db.execute(select(DataQualityJob.quality_job_id)).scalars().all()
    )

    response_jobs = []
    for j in jobs:
        j_dict = {
            "job_id": j.job_id,
            "source_id": j.source_id,
            "status": j.status,
            "current_stage": j.current_stage,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "error_message": j.error_message,
            "retry_count": j.retry_count,
            "parent_job_id": j.parent_job_id,
            "created_at": j.created_at,
            "updated_at": j.updated_at,
            "job_type": "QUALITY" if j.job_id in quality_job_ids else "INGESTION"
        }
        response_jobs.append(j_dict)

    return response_jobs


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

    from app.models.db.data_quality_job import DataQualityJob
    is_quality = db.execute(
        select(DataQualityJob).where(DataQualityJob.quality_job_id == job_id)
    ).scalar_one_or_none() is not None

    return {
        "job_id": job.job_id,
        "source_id": job.source_id,
        "status": job.status,
        "current_stage": job.current_stage,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "error_message": job.error_message,
        "retry_count": job.retry_count,
        "parent_job_id": job.parent_job_id,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "job_type": "QUALITY" if is_quality else "INGESTION"
    }


@router.post(
    "/jobs/{job_id}/retry",
    response_model=JobResponse,
    status_code=201
)
def retry_job(
    job_id: UUID,
    force_dq: bool = False,
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
    # Fix retry isolation: find which artifacts were actually attempted in the old job.
    
    stage = db.execute(
        select(JobStageHistory)
        .where(
            JobStageHistory.job_id == old_job.job_id,
            JobStageHistory.stage_name == "Dataset Acquisition"
        )
    ).scalar_one_or_none()
    
    attempted_external_ids = []
    if stage and stage.details and "artifacts" in stage.details:
        for art in stage.details["artifacts"]:
            if isinstance(art, dict) and "external_id" in art:
                attempted_external_ids.append(art["external_id"])
                
    if attempted_external_ids:
        # Reset only the artifacts attempted in the failed job
        db.execute(
            update(ArtifactRecord)
            .where(
                ArtifactRecord.source_id == old_job.source_id,
                ArtifactRecord.external_artifact_id.in_(attempted_external_ids)
            )
            .values(
                status="DISCOVERED",
                processed_at=None,
                failure_reason=None
            )
        )
    else:
        # Fallback: reset only failed artifacts for this source to avoid resetting completed ones from other lineages
        db.execute(
            update(ArtifactRecord)
            .where(
                ArtifactRecord.source_id == old_job.source_id,
                ArtifactRecord.status == "FAILED"
            )
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
            new_job.source_id,
            force_dq=force_dq
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


def get_parent_job_summary(parent_job_id: UUID, db: Session) -> dict | None:
    if not parent_job_id:
        return None
    from app.models.db.job import Job
    from app.models.db.job_stage_history import JobStageHistory
    
    parent_job = db.get(Job, parent_job_id)
    if not parent_job:
        return None
        
    stages_stmt = select(JobStageHistory).where(JobStageHistory.job_id == parent_job_id).order_by(JobStageHistory.started_at.asc())
    stages = db.execute(stages_stmt).scalars().all()
    
    return {
        "job_id": parent_job.job_id,
        "status": parent_job.status,
        "parent_job_id": parent_job.parent_job_id,
        "started_at": parent_job.started_at,
        "completed_at": parent_job.completed_at,
        "error_message": parent_job.error_message,
        "created_at": parent_job.created_at,
        "stages": [
            {
                "stage_history_id": st.stage_history_id,
                "job_id": st.job_id,
                "stage_name": st.stage_name,
                "status": st.status,
                "started_at": st.started_at,
                "completed_at": st.completed_at,
                "error_message": st.error_message
            }
            for st in stages
        ],
        "parent_job": get_parent_job_summary(parent_job.parent_job_id, db) if parent_job.parent_job_id else None
    }


@router.get(
    "/jobs/{job_id}/details",
    response_model=JobDetailsResponse
)
def get_job_details(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    from app.models.db.landing_inference import LandingInference
    from app.models.db.schema_validation import SchemaValidation
    from app.models.db.schema_drift import SchemaDrift
    from app.models.db.schema_recommendation import SchemaRecommendation
    from app.models.db.schema_fallback_request import SchemaFallbackRequest
    from app.models.db.metadata_profile import MetadataProfile
    from app.models.db.target_catalog import TargetCatalog
    from app.models.db.job_stage_history import JobStageHistory
    from app.models.db.data_quality_job import DataQualityJob
    from app.models.db.data_quality_report import DataQualityReport

    # 1. Fetch the Job
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    # Build job parent lineage
    lineage_job_ids = [job_id]
    curr_parent_id = job.parent_job_id
    while curr_parent_id:
        lineage_job_ids.append(curr_parent_id)
        p_job = db.get(Job, curr_parent_id)
        curr_parent_id = p_job.parent_job_id if p_job else None

    # 2. Fetch current job stages
    stages_stmt = select(JobStageHistory).where(JobStageHistory.job_id == job_id).order_by(JobStageHistory.started_at.asc())
    stages = db.execute(stages_stmt).scalars().all()

    # 3. Recursively fetch parent job summary
    parent_job_summary = get_parent_job_summary(job.parent_job_id, db) if job.parent_job_id else None

    # 4. Fetch associated details per artifact
    inferences = db.execute(
        select(LandingInference).where(LandingInference.job_id == job_id)
    ).scalars().all()

    artifact_details = []
    for inf in inferences:
        artifact = db.get(ArtifactRecord, inf.artifact_id)
        if not artifact:
            continue

        validation = db.execute(
            select(SchemaValidation).where(SchemaValidation.inference_id == inf.inference_id)
        ).scalar_one_or_none()

        drift = None
        if validation:
            drift = db.execute(
                select(SchemaDrift).where(SchemaDrift.validation_id == validation.validation_id)
            ).scalar_one_or_none()

        rec = None
        if validation:
            rec = db.execute(
                select(SchemaRecommendation).where(SchemaRecommendation.validation_id == validation.validation_id)
            ).scalar_one_or_none()

        fallback = None
        if validation:
            fallback = db.execute(
                select(SchemaFallbackRequest).where(SchemaFallbackRequest.validation_id == validation.validation_id)
            ).scalar_one_or_none()

        target_id = None
        if rec and rec.target_id:
            target_id = rec.target_id
        elif drift and drift.target_id:
            target_id = drift.target_id
        elif validation and validation.target_id:
            target_id = validation.target_id
        elif inf.target_id:
            target_id = inf.target_id

        target = db.get(TargetCatalog, target_id) if target_id else None

        target_summary = None
        if target:
            target_summary = {
                "target_id": target.target_id,
                "target_name": target.target_name,
                "target_type": target.target_type,
                "schema_definition": target.schema_definition
            }

        validation_summary = None
        if validation:
            validation_summary = {
                "validation_id": validation.validation_id,
                "validation_status": validation.validation_status,
                "coverage_percentage": float(validation.coverage_percentage),
                "target_match_percentage": float(validation.target_match_percentage),
                "mapped_column_count": validation.mapped_column_count,
                "source_column_count": validation.source_column_count,
                "target_column_count": validation.target_column_count,
                "report_json": validation.report_json,
                "created_at": validation.created_at
            }

        drift_summary = None
        if drift:
            drift_summary = {
                "drift_id": drift.drift_id,
                "drift_status": drift.drift_status,
                "drift_score": float(drift.drift_score),
                "drift_summary": drift.drift_summary,
                "created_at": drift.created_at
            }

        rec_summary = None
        if rec:
            rec_summary = {
                "recommendation_id": rec.recommendation_id,
                "recommendation_status": rec.recommendation_status,
                "deterministic_findings": rec.deterministic_findings,
                "recommendations_list": rec.recommendations_list,
                "partitioning_recommendation": rec.partitioning_recommendation,
                "explanation": rec.explanation,
                "created_at": rec.created_at
            }

        fallback_summary = None
        if fallback:
            fallback_summary = {
                "request_id": fallback.request_id,
                "request_reason": fallback.request_reason,
                "request_status": fallback.request_status,
                "backup_table_name": fallback.backup_table_name,
                "approved_by": fallback.approved_by,
                "approved_at": fallback.approved_at,
                "rejected_by": fallback.rejected_by,
                "rejected_at": fallback.rejected_at,
                "review_notes": fallback.review_notes,
                "created_at": fallback.created_at
            }

        dq_report = db.execute(
            select(DataQualityReport)
            .join(DataQualityJob, DataQualityJob.quality_job_id == DataQualityReport.job_id)
            .where(
                or_(
                    DataQualityJob.quality_job_id.in_(lineage_job_ids),
                    DataQualityJob.parent_job_id.in_(lineage_job_ids)
                ),
                DataQualityJob.artifact_id == artifact.artifact_id
            )
            .order_by(DataQualityReport.created_at.desc())
        ).scalars().first()

        dq_report_summary = None
        if dq_report:
            dq_report_summary = {
                "report_id": dq_report.report_id,
                "job_id": dq_report.job_id,
                "status": dq_report.status,
                "rules_executed": dq_report.rules_executed,
                "rules_failed": dq_report.rules_failed,
                "report_json": dq_report.report_json,
                "created_at": dq_report.created_at
            }

        artifact_details.append({
            "artifact_id": artifact.artifact_id,
            "source_id": artifact.source_id,
            "external_artifact_id": artifact.external_artifact_id,
            "artifact_name": artifact.artifact_name,
            "status": artifact.status,
            "processed_at": artifact.processed_at,
            "discovered_at": artifact.discovered_at,
            "failure_reason": artifact.failure_reason,
            "artifact_metadata": artifact.artifact_metadata,
            "inference": {
                "inference_id": inf.inference_id,
                "confidence_score": float(inf.confidence_score),
                "column_mapping": inf.column_mapping,
                "unmapped_source_columns": inf.unmapped_source_columns,
                "missing_target_columns": inf.missing_target_columns,
                "partitioning_recommendation": inf.partitioning_recommendation,
                "reasoning": inf.reasoning,
                "requires_review": inf.requires_review,
                "created_at": inf.created_at,
                "matched_target_table": target.target_name if target else None,
                "matched_target_id": target.target_id if target else None
            },
            "validation": validation_summary,
            "drift": drift_summary,
            "recommendation": rec_summary,
            "fallback": fallback_summary,
            "target": target_summary,
            "data_quality": dq_report_summary
        })

    # If no inferences yet, fall back to base artifacts associated with the source
    if not artifact_details:
        all_artifacts = db.execute(
            select(ArtifactRecord).where(ArtifactRecord.source_id == job.source_id)
        ).scalars().all()
        for art in all_artifacts:
            art_dq_report = db.execute(
                select(DataQualityReport)
                .join(DataQualityJob, DataQualityJob.quality_job_id == DataQualityReport.job_id)
                .where(
                    or_(
                        DataQualityJob.quality_job_id.in_(lineage_job_ids),
                        DataQualityJob.parent_job_id.in_(lineage_job_ids)
                    ),
                    DataQualityJob.artifact_id == art.artifact_id
                )
                .order_by(DataQualityReport.created_at.desc())
            ).scalars().first()

            art_dq_report_summary = None
            if art_dq_report:
                art_dq_report_summary = {
                    "report_id": art_dq_report.report_id,
                    "job_id": art_dq_report.job_id,
                    "status": art_dq_report.status,
                    "rules_executed": art_dq_report.rules_executed,
                    "rules_failed": art_dq_report.rules_failed,
                    "report_json": art_dq_report.report_json,
                    "created_at": art_dq_report.created_at
                }

            artifact_details.append({
                "artifact_id": art.artifact_id,
                "source_id": art.source_id,
                "external_artifact_id": art.external_artifact_id,
                "artifact_name": art.artifact_name,
                "status": art.status,
                "processed_at": art.processed_at,
                "discovered_at": art.discovered_at,
                "failure_reason": art.failure_reason,
                "artifact_metadata": art.artifact_metadata,
                "inference": None,
                "validation": None,
                "drift": None,
                "recommendation": None,
                "fallback": None,
                "target": None,
                "data_quality": art_dq_report_summary
            })

    # 5. Determine schemas
    metadata_profile = db.execute(
        select(MetadataProfile).where(MetadataProfile.job_id == job_id)
    ).scalar_one_or_none()

    first_target_schema = None
    if artifact_details:
        first_target = next((item["target"] for item in artifact_details if item["target"]), None)
        if first_target:
            first_target_schema = first_target["schema_definition"]

    return {
        "job": job,
        "stages": stages,
        "parent_job": parent_job_summary,
        "artifacts": artifact_details,
        "source_schema": metadata_profile.metadata_json if metadata_profile else None,
        "target_schema": first_target_schema
    }


@router.get(
    "/jobs/{job_id}/stages"
)
def get_job_stages(
    job_id: UUID,
    db: Session = Depends(get_db)
):
    
    stmt = select(JobStageHistory).where(JobStageHistory.job_id == job_id).order_by(JobStageHistory.started_at.asc())
    result = db.execute(stmt)
    return result.scalars().all()