import logging
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.settings import settings
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_validation import SchemaValidation
from app.models.db.landing_inference import LandingInference
from app.models.db.target_catalog import TargetCatalog
from app.models.db.schema_recommendation import SchemaRecommendation
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.services.job_stage_service import start_stage, complete_stage, fail_stage, update_job_status_from_artifacts
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

        job = db.get(Job, job_uuid)

        # Idempotent lookup
        rec_record = db.execute(
            select(SchemaRecommendation).where(
                SchemaRecommendation.job_id == job_uuid,
                SchemaRecommendation.artifact_id == artifact_uuid
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

            # Re-evaluate overall job status from artifact states
            update_job_status_from_artifacts(job_uuid, db)

            # Always publish completion message for this artifact, passing artifact_id
            job = db.get(Job, job_uuid)
            publish_job_completed(
                job_id=job_id,
                source_id=str(job.source_id) if job else "",
                recommendations_count=0,
                target_name=None,
                artifact_id=str(artifact_uuid)
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

        # 1. Determine agentic configuration
        enable_agentic = settings.ENABLE_AGENTIC_PIPELINE
        config_obj = None
        if job and job.source_id:
            source_obj = db.get(Source, job.source_id)
            if source_obj and source_obj.config_id:
                config_obj = db.get(ProcessingConfiguration, source_obj.config_id)
        if config_obj and isinstance(config_obj.config_content, dict):
            enable_agentic = config_obj.config_content.get(
                "enable_agentic_pipeline", enable_agentic
            )

        partitioning_rec = inference.partitioning_recommendation

        if enable_agentic:
            logger.info("Routing to ADK Recommendation Agent (Agentic Path)")
            from app.services.agents.recommendation_agent import run_recommendation_agent
            agent_output = await run_recommendation_agent(
                job_id=job_id,
                target_id=str(target.target_id),
                validation_id=str(val_record.validation_id),
                drift_id=str(drift_record.drift_id),
                partitioning_recommendation=partitioning_rec,
                db=db,
            )
            recommendations_data = agent_output.get("recommendations", [])
            deterministic_findings = {
                "impact_assessment": agent_output.get("impact_assessment", {}),
                "data_quality_flags": agent_output.get("data_quality_flags"),
                "risk_level": agent_output.get("risk_level", "LOW"),
                "estimated_effort": agent_output.get("estimated_effort"),
                "transformation_plan": agent_output.get("transformation_plan"),
                "execution_path": "AGENTIC"
            }
            explanation = agent_output.get("explanation", "No explanation provided.")
        else:
            logger.info("Routing to Standard LLM Recommendation Generator (LLM Path)")
            # 1. Generate deterministic findings
            findings = extract_deterministic_findings(val_record.report_json, drift_record.drift_summary)
            findings["execution_path"] = "LLM"

            # Query database for stage-specific feedback
            feedback_records = db.scalars(
                select(LlmFeedbackLoop)
                .where(
                    LlmFeedbackLoop.stage.ilike("%recommendation%")
                )
                .order_by(LlmFeedbackLoop.created_at.desc())
                .limit(20)
            ).all()

            feedback_str = ""
            if feedback_records:
                feedback_lines = [
                    f"- {record.engineer_notes}"
                    for record in feedback_records
                    if record.engineer_notes
                ]
                if feedback_lines:
                    feedback_str = "\n".join(feedback_lines)

            # 2. Invoke LLM recommendation service
            llm_output = await generate_schema_recommendations(
                findings,
                target,
                partitioning_rec,
                feedback_str=feedback_str
            )
            recommendations_data = [rec.model_dump() for rec in llm_output.recommendations]
            deterministic_findings = findings
            explanation = llm_output.explanation

        # 3. Store in DB
        if rec_record:
            rec_record.artifact_id = artifact_uuid
            rec_record.validation_id = val_record.validation_id
            rec_record.drift_id = drift_uuid
            rec_record.target_id = target.target_id
            rec_record.recommendation_status = "COMPLETED"
            rec_record.deterministic_findings = deterministic_findings
            rec_record.recommendations_list = recommendations_data
            rec_record.partitioning_recommendation = partitioning_rec
            rec_record.explanation = explanation
        else:
            rec_record = SchemaRecommendation(
                job_id=job_uuid,
                artifact_id=artifact_uuid,
                validation_id=val_record.validation_id,
                drift_id=drift_uuid,
                target_id=target.target_id,
                recommendation_status="COMPLETED",
                deterministic_findings=deterministic_findings,
                recommendations_list=recommendations_data,
                partitioning_recommendation=partitioning_rec,
                explanation=explanation
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
                "recommendations_count": len(recommendations_data),
                "execution_path": "AGENTIC" if enable_agentic else "LLM"
            }
        )

        # Re-evaluate overall job status from artifact states
        update_job_status_from_artifacts(job_uuid, db)

        # Always publish completion message for this artifact, passing artifact_id
        job = db.get(Job, job_uuid)
        publish_job_completed(
            job_id=job_id,
            source_id=str(job.source_id) if job else "",
            recommendations_count=len(recommendations_data),
            target_name=target.target_name,
            artifact_id=str(artifact_uuid)
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
