import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_drift_detected, publish_fallback_requested
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

    from sqlalchemy import select

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

        # Idempotent lookup for SchemaDrift
        drift_record = db.execute(
            select(SchemaDrift).where(
                SchemaDrift.job_id == job_uuid,
                SchemaDrift.artifact_id == artifact_uuid
            )
        ).scalar_one_or_none()

        # Handle skipped drift check (e.g. validation skipped/no target catalog mapped)
        if not val_record.target_id:
            logger.info(f"Drift detection SKIPPED for job_id={job_id} (no target mapped).")
            if drift_record:
                drift_record.artifact_id = artifact_uuid
                drift_record.validation_id = validation_uuid
                drift_record.target_id = None
                drift_record.drift_status = "SKIPPED"
                drift_record.drift_score = 0.0
                drift_record.drift_summary = {
                    "new_columns": [],
                    "removed_columns": [],
                    "datatype_changes": [],
                    "renamed_columns": []
                }
            else:
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

            return drift_record

        # Fetch TargetCatalog
        target = db.get(TargetCatalog, val_record.target_id)
        if target is None:
            raise ValueError(f"TargetCatalog not found: {val_record.target_id}")

        warning_threshold = settings.DRIFT_WARNING_THRESHOLD
        critical_threshold = settings.DRIFT_CRITICAL_THRESHOLD
        job_obj = db.get(Job, job_uuid)
        if job_obj:
            source = db.get(Source, job_obj.source_id)
            if source:
                config = db.get(ProcessingConfiguration, source.config_id)
                if config and isinstance(config.config_content, dict):
                    d_thresholds = config.config_content.get("drift_thresholds")
                    if isinstance(d_thresholds, dict):
                        if "warning_threshold" in d_thresholds:
                            warning_threshold = float(d_thresholds["warning_threshold"])
                        if "critical_threshold" in d_thresholds:
                            critical_threshold = float(d_thresholds["critical_threshold"])

        # Run drift computation
        drift_results = compute_schema_drift(
            metadata_json=profile.metadata_json,
            schema_definition=target.schema_definition or {},
            column_mapping=inference.column_mapping or {},
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold
        )

        drift_status = drift_results["drift_status"]
        drift_score = drift_results["drift_score"]
        drift_summary = drift_results["drift_summary"]

        if drift_record:
            drift_record.artifact_id = artifact_uuid
            drift_record.validation_id = validation_uuid
            drift_record.target_id = target.target_id
            drift_record.drift_status = drift_status
            drift_record.drift_score = drift_score
            drift_record.drift_summary = drift_summary
        else:
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
            # Check if there is already an active fallback request for this artifact to be idempotent
            fallback_req = (
                db.query(SchemaFallbackRequest)
                .filter(
                    SchemaFallbackRequest.job_id == job_uuid,
                    SchemaFallbackRequest.artifact_id == artifact_uuid,
                    SchemaFallbackRequest.request_status == "PENDING"
                )
                .first()
            )
            if not fallback_req:
                fallback_req = SchemaFallbackRequest(
                    job_id=job_uuid,
                    artifact_id=artifact_uuid,
                    validation_id=validation_uuid,
                    drift_id=drift_record.drift_id,
                    request_reason="CRITICAL_DRIFT",
                    request_status="PENDING"
                )
                db.add(fallback_req)
            else:
                fallback_req.artifact_id = artifact_uuid
                fallback_req.validation_id = validation_uuid
                fallback_req.drift_id = drift_record.drift_id
                fallback_req.request_reason = "CRITICAL_DRIFT"

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
                request_reason="CRITICAL_DRIFT"
            )

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

        # Publish drift event only if drift is not critical
        if drift_status != "CRITICAL_DRIFT":
            publish_drift_detected(
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
