import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.metadata_profile import MetadataProfile
from app.models.target_catalog import TargetCatalog
from app.models.landing_inference import LandingInference
from app.models.schema_validation import SchemaValidation
from app.models.schema_drift import SchemaDrift
from app.models.schema_fallback_request import SchemaFallbackRequest
from app.models.job import Job
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_schema_drifted
from app.services.drift_service import compute_schema_drift
from app.core.settings import settings

logger = logging.getLogger("schema_drift")


def process_schema_drift(
    job_id: str,
    artifact_id: str,
    validation_id: str,
    db: Session
) -> SchemaDrift:
    """
    Synchronous orchestrator that handles schema drift detection, DB updates, audit stages,
    event publishing, and delegates core calculation to drift_service.
    Creates a SchemaFallbackRequest if drift is CRITICAL.
    """
    job_uuid = UUID(job_id)
    artifact_uuid = UUID(artifact_id)
    validation_uuid = UUID(validation_id)

    logger.info(f"Processor starting schema drift detection for job={job_id} validation={validation_id}")
    stage = start_stage(job_uuid, "Schema Drift Detection", db)

    try:
        # Fetch schema validation
        val_record = db.get(SchemaValidation, validation_uuid)
        if val_record is None:
            raise ValueError(f"SchemaValidation not found: {validation_id}")

        # Fetch landing inference
        inference = db.get(LandingInference, val_record.inference_id)
        if inference is None:
            raise ValueError(f"LandingInference not found: {val_record.inference_id}")

        # Fetch metadata profile
        profile = db.get(MetadataProfile, inference.metadata_profile_id)
        if profile is None:
            raise ValueError(f"MetadataProfile not found: {inference.metadata_profile_id}")

        # Handle skipped drift check (e.g. validation skipped/no target catalog mapped)
        if not val_record.target_id:
            logger.info(f"Drift detection SKIPPED for job_id={job_id} (no target mapped).")
            drift_record = SchemaDrift(
                job_id=job_uuid,
                artifact_id=artifact_uuid,
                validation_id=validation_uuid,
                target_id=None,
                drift_status="SKIPPED",
                drift_score=0.0,
                drift_summary={
                    "new_columns": [],
                    "removed_columns": [],
                    "datatype_changes": [],
                    "renamed_columns": []
                }
            )
            db.add(drift_record)
            db.commit()
            db.refresh(drift_record)

            complete_stage(
                stage.stage_history_id,
                db,
                details={
                    "drift_id": str(drift_record.drift_id),
                    "status": "SKIPPED",
                    "drift_score": 0.0
                }
            )
            publish_schema_drifted(
                job_id=job_id,
                artifact_id=artifact_id,
                drift_id=str(drift_record.drift_id),
                drift_status="SKIPPED",
                drift_score=0.0
            )
            return drift_record

        # Fetch TargetCatalog
        target = db.get(TargetCatalog, val_record.target_id)
        if target is None:
            raise ValueError(f"TargetCatalog not found: {val_record.target_id}")

        # Run drift computation
        drift_results = compute_schema_drift(
            metadata_json=profile.metadata_json,
            schema_definition=target.schema_definition or {},
            column_mapping=inference.column_mapping or {},
            warning_threshold=settings.DRIFT_WARNING_THRESHOLD,
            critical_threshold=settings.DRIFT_CRITICAL_THRESHOLD
        )

        drift_status = drift_results["drift_status"]
        drift_score = drift_results["drift_score"]
        drift_summary = drift_results["drift_summary"]

        drift_record = SchemaDrift(
            job_id=job_uuid,
            artifact_id=artifact_uuid,
            validation_id=validation_uuid,
            target_id=target.target_id,
            drift_status=drift_status,
            drift_score=drift_score,
            drift_summary=drift_summary
        )
        db.add(drift_record)
        db.commit()
        db.refresh(drift_record)

        # Handle CRITICAL_DRIFT
        if drift_status == "CRITICAL_DRIFT":
            # Check if there is already an active fallback request for this job to be idempotent
            stmt = (
                db.query(SchemaFallbackRequest)
                .filter(
                    SchemaFallbackRequest.job_id == job_uuid,
                    SchemaFallbackRequest.request_status == "PENDING"
                )
                .first()
            )
            if not stmt:
                fallback_req = SchemaFallbackRequest(
                    job_id=job_uuid,
                    artifact_id=artifact_uuid,
                    validation_id=validation_uuid,
                    drift_id=drift_record.drift_id,
                    request_reason="CRITICAL_DRIFT",
                    request_status="PENDING"
                )
                db.add(fallback_req)

                job = db.get(Job, job_uuid)
                if job:
                    job.status = "PENDING_REVIEW"
                db.commit()

        # Update stage history
        complete_stage(
            stage.stage_history_id,
            db,
            details={
                "drift_id": str(drift_record.drift_id),
                "status": drift_status,
                "drift_score": drift_score
            }
        )

        # Publish drift event
        publish_schema_drifted(
            job_id=job_id,
            artifact_id=artifact_id,
            drift_id=str(drift_record.drift_id),
            drift_status=drift_status,
            drift_score=drift_score
        )

        logger.info(f"Drift detection finished successfully for job_id={job_id} status={drift_status} score={drift_score}")
        return drift_record

    except Exception as e:
        logger.error(f"Schema Drift execution failed: {e}", exc_info=True)
        db.rollback()
        try:
            fail_stage(stage.stage_history_id, e, db)
        except Exception:
            pass
        raise
