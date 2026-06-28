import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.domain.inference_schema import InferenceResponseSchema
from app.services.metadata_service import generate_llm_optimized_json
from app.services.inference_service import generate_target_inference
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_target_inferred

logger = logging.getLogger("landing_inference")


async def infer_target_landing_zone(
    job_id: str,
    artifact_id: str,
    metadata_profile_id: str,
    db: Session
) -> None:
    """
    Retrieves the vectorized incoming metadata profile, searches target passports,
    runs the LLM reasoning selection on Vertex AI, and persists inference output.
    """
    job_uuid = UUID(job_id)
    profile_uuid = UUID(metadata_profile_id)
    
    logger.info(f"--- Starting Target Inference for job_id={job_id} profile_id={metadata_profile_id} ---")
    
    profile = db.get(MetadataProfile, profile_uuid)
    if profile is None:
        logger.error(f"MetadataProfile record not found: {profile_uuid}")
        return

    predefined_ids = []
    job = db.get(Job, job_uuid)
    if job:
        source = db.get(Source, job.source_id)
        if source:
            config = db.get(ProcessingConfiguration, source.config_id)
            if config and isinstance(config.config_content, dict):
                p_ids = config.config_content.get("predefined_target_ids")
                if isinstance(p_ids, list):
                    predefined_ids = p_ids

    is_predefined = (1 <= len(predefined_ids) <= settings.TARGET_INFERENCE_TOP_K)

    if not is_predefined and profile.source_embedding is None:
        logger.error(f"MetadataProfile has no embedding vectorized yet: {profile_uuid}")
        return

    # 1. Start the target inference audit stage
    stage = start_stage(job_uuid, "Target Inference", db)

    try:
        source_json = generate_llm_optimized_json(profile.metadata_json)

        # Query database for stage-specific feedback
        feedback_records = db.scalars(
            select(LlmFeedbackLoop)
            .where(
                LlmFeedbackLoop.stage.ilike("%inference%")
            )
            .order_by(LlmFeedbackLoop.created_at.desc())
            .limit(20)
        ).all()

        feedback_prompt_part = ""
        if feedback_records:
            feedback_lines = [
                f"- {record.engineer_notes}"
                for record in feedback_records
                if record.engineer_notes
            ]
            if feedback_lines:
                feedback_prompt_part = "\n\nHuman Engineering Feedback Guidelines:\n" + "\n".join(feedback_lines)

        # Resolve predefined targets if config contains any
        db_targets = []
        if predefined_ids:
            target_uuids = []
            for tid in predefined_ids:
                try:
                    target_uuids.append(UUID(str(tid)))
                except ValueError:
                    pass
            if target_uuids:
                stmt = select(TargetCatalog).where(TargetCatalog.target_id.in_(target_uuids))
                db_targets = list(db.execute(stmt).scalars().all())

        predefined_single = (len(db_targets) == 1)

        # Determine candidates: Predefined Multiple vs Semantic Search
        candidates = []
        if db_targets:
            # Case 2: Predefined multiple targets (Skip semantic search)
            candidates = db_targets
            logger.info(f"Case 2: Resolving from {len(candidates)} predefined target candidates.")
        else:
            # Case 3: No predefined targets / Semantic Search
            if not predefined_single:
                if profile.source_embedding is None:
                    raise ValueError("Cannot perform semantic search: source embedding is missing.")
                distance_expr = TargetCatalog.target_embedding.cosine_distance(profile.source_embedding)
                stmt = (
                    select(TargetCatalog, (1.0 - distance_expr).label("similarity"))
                    .where(TargetCatalog.target_embedding.is_not(None))
                    .order_by(distance_expr)
                    .limit(settings.TARGET_INFERENCE_TOP_K)
                )
                search_results = db.execute(stmt).all()
                candidates = [row[0] for row in search_results]
                logger.info(f"Case 3: Retrieved {len(candidates)} candidate targets via semantic search.")
            else:
                candidates = db_targets

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

        if enable_agentic:
            logger.info("Routing to ADK Inference Agent (Agentic RAG)")
            from app.services.agents.inference_agent import run_inference_agent
            res_json = await run_inference_agent(
                job_id=job_id,
                source_json=source_json,
                source_embedding=profile.source_embedding,
                predefined_target_ids=predefined_ids,
                db=db,
                connector_metadata=profile.metadata_json.get("connector_metadata"),
            )
        else:
            logger.info("Executing Standard Target Inference (LLM)")
            if not candidates and not predefined_single:
                logger.warning("No candidate targets found. Skipping selection.")
                res_json = {
                    "selected_target_id": None,
                    "confidence_score": 0.0,
                    "reasoning": "No candidate targets found.",
                    "column_mapping": None,
                    "unmapped_source_columns": [],
                    "missing_target_columns": [],
                    "partitioning_recommendation": None,
                    "naming_convention_suggestions": None
                }
            else:
                res_json = await generate_target_inference(
                    db=db,
                    source_json=source_json,
                    candidates=candidates,
                    predefined_single=predefined_single,
                    feedback_prompt_part=feedback_prompt_part
                )

        confidence = float(res_json.get("confidence_score", 0.0))
        selected_target_id_str = res_json.get("selected_target_id")
        reasoning = res_json.get("reasoning", "No reasoning provided.")
        column_mapping = res_json.get("column_mapping")
        unmapped_source = res_json.get("unmapped_source_columns", [])
        missing_target = res_json.get("missing_target_columns", [])
        partitioning_rec = res_json.get("partitioning_recommendation")
        naming_suggestions = res_json.get("naming_convention_suggestions")

        confidence_threshold = settings.INFERENCE_CONFIDENCE_THRESHOLD
        if config_obj and isinstance(config_obj.config_content, dict):
            confidence_threshold = float(config_obj.config_content.get(
                "inference_confidence_threshold", confidence_threshold
            ))

        requires_review = confidence < confidence_threshold
        if predefined_single:
            requires_review = False
        
        target_uuid = UUID(selected_target_id_str) if selected_target_id_str else None
        
        # 5. Store result in dedicated landing_inferences table (idempotent lookup)
        inference = db.execute(
            select(LandingInference).where(
                LandingInference.job_id == job_uuid,
                LandingInference.artifact_id == profile.artifact_id
            )
        ).scalar_one_or_none()

        if inference:
            inference.artifact_id = profile.artifact_id
            inference.metadata_profile_id = profile_uuid
            inference.target_id = target_uuid
            inference.confidence_score = confidence
            inference.column_mapping = column_mapping
            inference.unmapped_source_columns = unmapped_source
            inference.missing_target_columns = missing_target
            inference.partitioning_recommendation = partitioning_rec
            inference.naming_convention_suggestions = naming_suggestions
            inference.reasoning = reasoning
            inference.requires_review = requires_review
        else:
            inference = LandingInference(
                job_id=job_uuid,
                artifact_id=profile.artifact_id,
                metadata_profile_id=profile_uuid,
                target_id=target_uuid,
                confidence_score=confidence,
                column_mapping=column_mapping,
                unmapped_source_columns=unmapped_source,
                missing_target_columns=missing_target,
                partitioning_recommendation=partitioning_rec,
                naming_convention_suggestions=naming_suggestions,
                reasoning=reasoning,
                requires_review=requires_review
            )
            db.add(inference)
            
        db.commit()
        db.refresh(inference)
        
        logger.info(f"LandingInference saved with ID: {inference.inference_id}")

        # 6. Complete stage audit record (compact details)
        complete_stage(
            stage.stage_history_id,
            db,
            details={
                "inference_id": str(inference.inference_id),
                "target_id": str(inference.target_id) if inference.target_id else None,
                "confidence_score": float(inference.confidence_score),
                "requires_review": inference.requires_review,
                "execution_path": "AGENTIC" if enable_agentic else "LLM"
            }
        )

        # 7. Publish Event to trigger downstream pipeline steps
        publish_target_inferred(
            job_id=job_id,
            artifact_id=str(profile.artifact_id),
            metadata_profile_id=metadata_profile_id,
            inference_id=str(inference.inference_id),
            target_id=str(inference.target_id) if inference.target_id else None,
            confidence_score=float(inference.confidence_score),
            requires_review=inference.requires_review
        )
        
        logger.info(f"Target Inference finished successfully for job_id={job_id}")

    except Exception as e:
        logger.error(f"Target Inference execution failed for job_id={job_id}: {e}", exc_info=True)
        db.rollback()
        try:
            fail_stage(stage.stage_history_id, e, db)
        except Exception:
            pass
        raise
