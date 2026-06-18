import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.db.job import Job
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_validation import SchemaValidation
from app.models.db.landing_inference import LandingInference
from app.models.db.target_catalog import TargetCatalog
from app.models.db.schema_recommendation import SchemaRecommendation
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.services.recommendation_service import extract_deterministic_findings, generate_schema_recommendations
from app.pubsub.publisher import publish_job_completed

logger = logging.getLogger("schema_recommendation")


async def process_schema_recommendation(
    job_id: str,
    artifact_id: str,
    drift_id: str,
    db: Session
) -> SchemaRecommendation:
    """
    Orchestrates the recommendation generation process.
    Loads validation/drift reports, runs deterministic finding extraction,
    generates AI-assisted recommendations via the LLM, and completes the Job.
    """
    job_uuid = UUID(job_id)
    artifact_uuid = UUID(artifact_id)
    drift_uuid = UUID(drift_id)

    logger.info(f"Processor starting schema recommendation for job={job_id} drift={drift_id}")
    stage = start_stage(job_uuid, "Schema Recommendation Generation", db)

    try:
        # Fetch SchemaDrift
        drift_record = db.get(SchemaDrift, drift_uuid)
        if drift_record is None:
            raise ValueError(f"SchemaDrift not found: {drift_id}")

        # Fetch SchemaValidation
        val_record = db.get(SchemaValidation, drift_record.validation_id)
        if val_record is None:
            raise ValueError(f"SchemaValidation not found: {drift_record.validation_id}")

        # Idempotent lookup
        rec_record = db.execute(
            select(SchemaRecommendation).where(
                SchemaRecommendation.job_id == job_uuid
            )
        ).scalar_one_or_none()

        # Handle skipped stage
        if drift_record.drift_status == "SKIPPED" or val_record.validation_status == "SKIPPED":
            logger.info(f"Recommendation SKIPPED for job_id={job_id} due to upstream validation/drift skipped.")
            
            if rec_record:
                rec_record.artifact_id = artifact_uuid
                rec_record.validation_id = val_record.validation_id
                rec_record.drift_id = drift_uuid
                rec_record.target_id = None
                rec_record.recommendation_status = "SKIPPED"
                rec_record.deterministic_findings = {}
                rec_record.recommendations_list = []
                rec_record.partitioning_recommendation = None
                rec_record.explanation = "Upstream validation or drift was skipped."
            else:
                rec_record = SchemaRecommendation(
                    job_id=job_uuid,
                    artifact_id=artifact_uuid,
                    validation_id=val_record.validation_id,
                    drift_id=drift_uuid,
                    target_id=None,
                    recommendation_status="SKIPPED",
                    deterministic_findings={},
                    recommendations_list=[],
                    partitioning_recommendation=None,
                    explanation="Upstream validation or drift was skipped."
                )
                db.add(rec_record)

            db.commit()
            db.refresh(rec_record)

            # Complete job stage
            complete_stage(
                stage.stage_history_id,
                db,
                details={
                    "recommendation_id": str(rec_record.recommendation_id),
                    "status": "SKIPPED"
                }
            )

            # Mark parent job completed
            job = db.get(Job, job_uuid)
            if job:
                job.status = "COMPLETED"
                db.commit()

            # Publish job completed
            publish_job_completed(
                job_id=job_id,
                source_id=str(job.source_id) if job else "",
                recommendations_count=0,
                target_name=None
            )
            return rec_record

        # Fetch TargetCatalog
        target = db.get(TargetCatalog, drift_record.target_id)
        if target is None:
            raise ValueError(f"TargetCatalog not found: {drift_record.target_id}")

        # Fetch LandingInference
        inference = db.get(LandingInference, val_record.inference_id)
        if inference is None:
            raise ValueError(f"LandingInference not found: {val_record.inference_id}")

        # 1. Generate deterministic findings
        findings = extract_deterministic_findings(val_record.report_json, drift_record.drift_summary)

        # 2. Invoke LLM recommendation service
        partitioning_rec = inference.partitioning_recommendation
        llm_output = await generate_schema_recommendations(findings, target, partitioning_rec)

        recommendations_data = [rec.model_dump() for rec in llm_output.recommendations]

        # 3. Store in DB
        if rec_record:
            rec_record.artifact_id = artifact_uuid
            rec_record.validation_id = val_record.validation_id
            rec_record.drift_id = drift_uuid
            rec_record.target_id = target.target_id
            rec_record.recommendation_status = "COMPLETED"
            rec_record.deterministic_findings = findings
            rec_record.recommendations_list = recommendations_data
            rec_record.partitioning_recommendation = partitioning_rec
            rec_record.explanation = llm_output.explanation
        else:
            rec_record = SchemaRecommendation(
                job_id=job_uuid,
                artifact_id=artifact_uuid,
                validation_id=val_record.validation_id,
                drift_id=drift_uuid,
                target_id=target.target_id,
                recommendation_status="COMPLETED",
                deterministic_findings=findings,
                recommendations_list=recommendations_data,
                partitioning_recommendation=partitioning_rec,
                explanation=llm_output.explanation
            )
            db.add(rec_record)

        db.commit()
        db.refresh(rec_record)

        # Complete job stage
        complete_stage(
            stage.stage_history_id,
            db,
            details={
                "recommendation_id": str(rec_record.recommendation_id),
                "status": "COMPLETED",
                "recommendations_count": len(recommendations_data)
            }
        )

        # Mark parent job completed
        job = db.get(Job, job_uuid)
        if job:
            job.status = "COMPLETED"
            db.commit()

        # Publish job completed
        publish_job_completed(
            job_id=job_id,
            source_id=str(job.source_id) if job else "",
            recommendations_count=len(recommendations_data),
            target_name=target.target_name
        )

        logger.info(f"Schema Recommendation finished successfully for job_id={job_id} recs={len(recommendations_data)}")
        return rec_record

    except Exception as e:
        logger.error(f"Schema Recommendation execution failed: {e}", exc_info=True)
        db.rollback()
        try:
            fail_stage(stage.stage_history_id, e, db)
        except Exception:
            pass
        raise
