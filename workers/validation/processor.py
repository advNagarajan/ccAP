import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.metadata_profile import MetadataProfile
from app.models.target_catalog import TargetCatalog
from app.models.landing_inference import LandingInference
from app.models.schema_validation import SchemaValidation
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_schema_validated
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

        # Handle skipped validation
        if not inference.target_id:
            logger.info(f"Validation SKIPPED for job_id={job_id} (no target mapped).")
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
                report_json={
                    "report_version": "1.0",
                    "invalid_mappings": [],
                    "datatype_issues": [],
                    "missing_target_columns": [],
                    "additional_source_columns": [],
                    "coverage_percentage": 0.0,
                    "target_match_percentage": 0.0
                }
            )
            db.add(val_record)
            db.commit()
            db.refresh(val_record)

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
            publish_schema_validated(
                job_id=job_id,
                artifact_id=artifact_id,
                inference_id=inference_id,
                validation_id=str(val_record.validation_id),
                validation_status="SKIPPED"
            )
            return val_record

        target = db.get(TargetCatalog, inference.target_id)
        if target is None:
            raise ValueError(f"TargetCatalog table not found: {inference.target_id}")

        # Core logic execution
        results = compute_schema_validation(
            metadata_json=profile.metadata_json,
            schema_definition=target.schema_definition or {},
            column_mapping=inference.column_mapping or {},
            unmapped_source_columns=inference.unmapped_source_columns or [],
            missing_target_columns=inference.missing_target_columns or [],
            warning_threshold=settings.VALIDATION_WARNING_THRESHOLD
        )

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

        # Publish validation event
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
