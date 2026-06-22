import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_schema_validated, publish_fallback_requested
from app.services.validation_service import compute_schema_validation
from app.core.settings import settings

logger = logging.getLogger("schema_validation")


def process_schema_validation(
    job_id: str,
    artifact_id: str,
    metadata_profile_id: str,
    inference_id: str,
    db: Session
) -> SchemaValidation:
    """
    Synchronous orchestrator that handles DB updates, audit stages, event publishing,
    and delegates core logic to validation_service.
    Creates a SchemaFallbackRequest if validation is skipped (target not found) or failed.
    """
    job_uuid = UUID(job_id)
    inference_uuid = UUID(inference_id)
    profile_uuid = UUID(metadata_profile_id)

    logger.info(f"Processor starting schema validation for job={job_id} inference={inference_id}")
    stage = start_stage(job_uuid, "Schema Validation", db)

    try:
        inference = db.get(LandingInference, inference_uuid)
        if inference is None:
            raise ValueError(f"LandingInference not found: {inference_id}")

        profile = db.get(MetadataProfile, profile_uuid)
        if profile is None:
            raise ValueError(f"MetadataProfile not found: {metadata_profile_id}")

        from sqlalchemy import select

        # Idempotent lookups
        val_record = db.execute(
            select(SchemaValidation).where(
                SchemaValidation.job_id == job_uuid,
                SchemaValidation.artifact_id == UUID(artifact_id)
            )
        ).scalar_one_or_none()

        fallback_req = db.execute(
            select(SchemaFallbackRequest).where(
                SchemaFallbackRequest.job_id == job_uuid,
                SchemaFallbackRequest.artifact_id == UUID(artifact_id)
            )
        ).scalar_one_or_none()

        # Handle skipped validation (TARGET_NOT_FOUND)
        if not inference.target_id:
            logger.info(f"Validation SKIPPED for job_id={job_id} (no target mapped).")
            
            report_data = {
                "report_version": "1.0",
                "invalid_mappings": [],
                "datatype_issues": [],
                "missing_target_columns": [],
                "additional_source_columns": [],
                "coverage_percentage": 0.0,
                "target_match_percentage": 0.0
            }

            if val_record:
                val_record.artifact_id = UUID(artifact_id)
                val_record.inference_id = inference_uuid
                val_record.target_id = None
                val_record.validation_status = "SKIPPED"
                val_record.coverage_percentage = 0.0
                val_record.target_match_percentage = 0.0
                val_record.mapped_column_count = 0
                val_record.source_column_count = 0
                val_record.target_column_count = 0
                val_record.report_json = report_data
            else:
                val_record = SchemaValidation(
                    job_id=job_uuid,
                    artifact_id=UUID(artifact_id),
                    inference_id=inference_uuid,
                    target_id=None,
                    validation_status="SKIPPED",
                    coverage_percentage=0.0,
                    target_match_percentage=0.0,
                    mapped_column_count=0,
                    source_column_count=0,
                    target_column_count=0,
                    report_json=report_data
                )
                db.add(val_record)
            
            db.commit()
            db.refresh(val_record)

            # Create or update fallback request
            if fallback_req:
                fallback_req.artifact_id = UUID(artifact_id)
                fallback_req.validation_id = val_record.validation_id
                fallback_req.request_reason = "TARGET_NOT_FOUND"
                fallback_req.request_status = "PENDING"
            else:
                fallback_req = SchemaFallbackRequest(
                    job_id=job_uuid,
                    artifact_id=UUID(artifact_id),
                    validation_id=val_record.validation_id,
                    request_reason="TARGET_NOT_FOUND",
                    request_status="PENDING"
                )
                db.add(fallback_req)

            # Update parent job status to PENDING_REVIEW
            job = db.get(Job, job_uuid)
            if job:
                job.status = "PENDING_REVIEW"

            db.commit()

            # Publish fallback requested event
            source_id = job.source_id if job else None
            publish_fallback_requested(
                job_id=job_id,
                source_id=source_id,
                request_id=fallback_req.request_id,
                request_reason="TARGET_NOT_FOUND"
            )

            complete_stage(
                stage.stage_history_id,
                db,
                details={
                    "validation_id": str(val_record.validation_id),
                    "status": "SKIPPED",
                    "coverage_percentage": 0.0,
                    "target_match_percentage": 0.0,
                    "issue_count": 0
                }
            )

            return val_record

        target = db.get(TargetCatalog, inference.target_id)
        if target is None:
            raise ValueError(f"TargetCatalog table not found: {inference.target_id}")

        warning_threshold = settings.VALIDATION_WARNING_THRESHOLD
        job_obj = db.get(Job, job_uuid)
        if job_obj:
            source = db.get(Source, job_obj.source_id)
            if source:
                config = db.get(ProcessingConfiguration, source.config_id)
                if config and isinstance(config.config_content, dict):
                    v_thresholds = config.config_content.get("validation_thresholds")
                    if isinstance(v_thresholds, dict) and "warning_threshold" in v_thresholds:
                        warning_threshold = float(v_thresholds["warning_threshold"])

        # Core logic execution
        results = compute_schema_validation(
            metadata_json=profile.metadata_json,
            schema_definition=target.schema_definition or {},
            column_mapping=inference.column_mapping or {},
            unmapped_source_columns=inference.unmapped_source_columns or [],
            missing_target_columns=inference.missing_target_columns or [],
            warning_threshold=warning_threshold
        )

        if val_record:
            val_record.artifact_id = UUID(artifact_id)
            val_record.inference_id = inference_uuid
            val_record.target_id = target.target_id
            val_record.validation_status = results["validation_status"]
            val_record.coverage_percentage = results["coverage_percentage"]
            val_record.target_match_percentage = results["target_match_percentage"]
            val_record.mapped_column_count = results["mapped_column_count"]
            val_record.source_column_count = results["source_column_count"]
            val_record.target_column_count = results["target_column_count"]
            val_record.report_json = results["report_json"]
        else:
            val_record = SchemaValidation(
                job_id=job_uuid,
                artifact_id=UUID(artifact_id),
                inference_id=inference_uuid,
                target_id=target.target_id,
                validation_status=results["validation_status"],
                coverage_percentage=results["coverage_percentage"],
                target_match_percentage=results["target_match_percentage"],
                mapped_column_count=results["mapped_column_count"],
                source_column_count=results["source_column_count"],
                target_column_count=results["target_column_count"],
                report_json=results["report_json"]
            )
            db.add(val_record)
        
        db.commit()
        db.refresh(val_record)

        # Handle failed validation (VALIDATION_FAILED)
        if val_record.validation_status == "FAILED":
            if fallback_req:
                fallback_req.artifact_id = UUID(artifact_id)
                fallback_req.validation_id = val_record.validation_id
                fallback_req.request_reason = "VALIDATION_FAILED"
                fallback_req.request_status = "PENDING"
            else:
                fallback_req = SchemaFallbackRequest(
                    job_id=job_uuid,
                    artifact_id=UUID(artifact_id),
                    validation_id=val_record.validation_id,
                    request_reason="VALIDATION_FAILED",
                    request_status="PENDING"
                )
                db.add(fallback_req)

            job = db.get(Job, job_uuid)
            if job:
                job.status = "PENDING_REVIEW"

            db.commit()

            # Publish fallback requested event
            source_id = job.source_id if job else None
            publish_fallback_requested(
                job_id=job_id,
                source_id=source_id,
                request_id=fallback_req.request_id,
                request_reason="VALIDATION_FAILED"
            )

        # Log compact audit stage
        issue_count = len(results["report_json"]["invalid_mappings"]) + len(results["report_json"]["datatype_issues"])
        complete_stage(
            stage.stage_history_id,
            db,
            details={
                "validation_id": str(val_record.validation_id),
                "status": results["validation_status"],
                "coverage_percentage": results["coverage_percentage"],
                "target_match_percentage": results["target_match_percentage"],
                "issue_count": issue_count
            }
        )

        # Publish validation event only if it did not fail
        if results["validation_status"] != "FAILED":
            publish_schema_validated(
                job_id=job_id,
                artifact_id=artifact_id,
                inference_id=inference_id,
                validation_id=str(val_record.validation_id),
                validation_status=results["validation_status"]
            )

        logger.info(f"Schema Validation finished successfully for job_id={job_id} status={results['validation_status']}")
        return val_record

    except Exception as e:
        logger.error(f"Schema Validation execution failed: {e}", exc_info=True)
        db.rollback()
        try:
            fail_stage(stage.stage_history_id, e, db)
        except Exception:
            pass
        raise
