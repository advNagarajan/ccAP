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
from app.models.domain.inference_schema import (
    InferenceResponseSchema,
    TargetSelectionSchema,
    TargetMappingSchema
)
from app.services.metadata_service import (
    generate_llm_optimized_json,
    generate_target_llm_optimized_json
)
from app.services.llm import get_llm_provider
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
                (LlmFeedbackLoop.job_id == job_uuid) &
                (LlmFeedbackLoop.stage.ilike("%inference%"))
            )
            .order_by(LlmFeedbackLoop.created_at.asc())
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

        llm_provider = get_llm_provider()

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

        # Case 1: Predefined Single Target - Bypass selection, go straight to mapping pass
        if predefined_single:
            selected_target = db_targets[0]
            selected_target_id_str = str(selected_target.target_id)
            confidence = 1.0
            selection_reasoning = "Using predefined single target candidate from configuration."
            logger.info(f"Case 1: Single predefined target candidate used: {selected_target_id_str}")

            target_json = generate_target_llm_optimized_json(selected_target)
            prompt_mapping = (
                "Map the incoming source dataset schema to the selected target database table schema.\n\n"
                "Source Schema:\n"
                f"{json.dumps(source_json, indent=2)}\n\n"
                "Selected Target Table:\n"
                f"Target ID: {selected_target.target_id}\n"
                f"Target Name: {selected_target.target_name}\n"
                f"Description: {selected_target.description or 'No description'}\n"
                f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                f"{feedback_prompt_part}\n\n"
                "Instructions & Constraints:\n"
                "1. Column Mapping: Map source columns to target columns. Map to null if unmatched. Only use explicitly defined target schema fields.\n"
                "2. Coverage: Identify unmapped source columns ('unmapped_source_columns') and missing target columns ('missing_target_columns').\n"
                "3. Partitioning: Recommend column/strategy ONLY if a date, timestamp, or high-cardinality ID field exists in source. Otherwise return null.\n"
                "4. Casing: Suggest standard naming adjustments to reconcile source names with target conventions (e.g. lowercase snake_case for PostgreSQL).\n"
                "5. STRICT BOUNDARIES: Do NOT perform target selection or compare tables. Assume the provided target is correct. Explain mapping/partition decisions in 'reasoning' in under 3 sentences.\n"
                "6. Your response MUST be valid JSON adhering exactly to the TargetMappingSchema."
            )

            logger.info(f"Sending mapping pass prompt to LLM:\n{prompt_mapping}")
            mapping_response = await llm_provider.generate_response(
                prompt=prompt_mapping,
                response_schema=TargetMappingSchema
            )
            logger.info(f"Raw LLM Structured Mapping Response:\n{mapping_response}")
            mapping_json = json.loads(mapping_response)

            res_json = {
                "selected_target_id": selected_target_id_str,
                "confidence_score": confidence,
                "reasoning": f"Selection Reason: {selection_reasoning}\nMapping Details: {mapping_json.get('reasoning', '')}",
                "column_mapping": mapping_json.get("column_mapping"),
                "unmapped_source_columns": mapping_json.get("unmapped_source_columns", []),
                "missing_target_columns": mapping_json.get("missing_target_columns", []),
                "partitioning_recommendation": mapping_json.get("partitioning_recommendation"),
                "naming_convention_suggestions": mapping_json.get("naming_convention_suggestions")
            }

        else:
            # Determine candidates: Predefined Multiple vs Semantic Search
            candidates = []
            if db_targets:
                # Case 2: Predefined multiple targets (Skip semantic search)
                candidates = db_targets
                logger.info(f"Case 2: Resolving from {len(candidates)} predefined target candidates.")
            else:
                # Case 3: No predefined targets / Semantic Search
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

            if not candidates:
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
                # Pass 1: Selection Prompt
                candidates_context = []
                for idx, target in enumerate(candidates, 1):
                    target_json = generate_target_llm_optimized_json(target)
                    candidates_context.append(
                        f"Candidate {idx}\n"
                        f"Target ID: {target.target_id}\n"
                        f"Target Name: {target.target_name}\n"
                        f"Business Domain: {target.business_domain or 'General'}\n"
                        f"Description: {target.description or 'No description'}\n"
                        f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                        f"----------------------------------------"
                    )
                candidates_str = "\n".join(candidates_context)

                prompt_selection = (
                    "Evaluate candidate database tables and select the most apt target landing zone for the incoming source dataset schema.\n\n"
                    "Source Schema:\n"
                    f"{json.dumps(source_json, indent=2)}\n\n"
                    "Candidate Target Tables:\n"
                    f"{candidates_str}"
                    f"{feedback_prompt_part}\n\n"
                    "Instructions & Constraints:\n"
                    "1. Evaluate by: semantic meaning, column name alignment, schema coverage, data type compatibility, and similarity score to select the most apt target table.\n"
                    "2. Retrieval-Awareness: Candidates are pre-selected via vector similarity. Consider scores as supporting evidence, not the sole decision factor.\n"
                    "3. No-Match Handling: If no candidate is compatible, return selected_target_id = null. Do not force a match.\n"
                    "4. STRICT BOUNDARIES: Do NOT generate column mappings, unmapped/missing column lists, partitioning recommendations, or casing suggestions. Explain your selection in 'reasoning' in under 3 sentences.\n"
                    "5. Your response MUST be valid JSON adhering exactly to the TargetSelectionSchema."
                )

                logger.info(f"Sending selection pass prompt to LLM:\n{prompt_selection}")
                selection_response = await llm_provider.generate_response(
                    prompt=prompt_selection,
                    response_schema=TargetSelectionSchema
                )
                logger.info(f"Raw LLM Structured Selection Response:\n{selection_response}")
                selection_json = json.loads(selection_response)

                selected_target_id_str = selection_json.get("selected_target_id")
                if selected_target_id_str in (None, "", "null", "None"):
                    selected_target_id_str = None

                confidence = float(selection_json.get("confidence_score", 0.0))
                selection_reasoning = selection_json.get("reasoning", "No selection reasoning provided.")

                selected_target = None
                if selected_target_id_str:
                    try:
                        selected_uuid = UUID(selected_target_id_str)
                    except ValueError:
                        raise RuntimeError(f"LLM Hallucination: selected target ID '{selected_target_id_str}' is not a valid UUID format.")
                    
                    selected_target = next((t for t in candidates if t.target_id == selected_uuid), None)
                    if not selected_target:
                        selected_target = db.get(TargetCatalog, selected_uuid)
                        if not selected_target:
                            raise RuntimeError(f"LLM Hallucination: selected target ID '{selected_target_id_str}' was not found in the database catalog.")

                if selected_target:
                    # Pass 2: Mapping prompt
                    target_json = generate_target_llm_optimized_json(selected_target)
                    prompt_mapping = (
                        "Map the incoming source dataset schema to the selected target database table schema.\n\n"
                        "Source Schema:\n"
                        f"{json.dumps(source_json, indent=2)}\n\n"
                        "Selected Target Table:\n"
                        f"Target ID: {selected_target.target_id}\n"
                        f"Target Name: {selected_target.target_name}\n"
                        f"Description: {selected_target.description or 'No description'}\n"
                        f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                        f"{feedback_prompt_part}\n\n"
                        "Instructions & Constraints:\n"
                        "1. Column Mapping: Map source columns to target columns. Map to null if unmatched. Only use explicitly defined target schema fields.\n"
                        "2. Coverage: Identify unmapped source columns ('unmapped_source_columns') and missing target columns ('missing_target_columns').\n"
                        "3. Partitioning: Recommend column/strategy ONLY if a date, timestamp, or high-cardinality ID field exists in source. Otherwise return null.\n"
                        "4. Casing: Suggest standard naming adjustments to reconcile source names with target conventions (e.g. lowercase snake_case for PostgreSQL).\n"
                        "5. STRICT BOUNDARIES: Do NOT perform target selection or compare tables. Assume the provided target is correct. Explain mapping/partition decisions in 'reasoning' in under 3 sentences.\n"
                        "6. Your response MUST be valid JSON adhering exactly to the TargetMappingSchema."
                    )

                    logger.info(f"Sending mapping pass prompt to LLM:\n{prompt_mapping}")
                    mapping_response = await llm_provider.generate_response(
                        prompt=prompt_mapping,
                        response_schema=TargetMappingSchema
                    )
                    logger.info(f"Raw LLM Structured Mapping Response:\n{mapping_response}")
                    mapping_json = json.loads(mapping_response)

                    res_json = {
                        "selected_target_id": selected_target_id_str,
                        "confidence_score": confidence,
                        "reasoning": f"Selection Reason: {selection_reasoning}\nMapping Details: {mapping_json.get('reasoning', '')}",
                        "column_mapping": mapping_json.get("column_mapping"),
                        "unmapped_source_columns": mapping_json.get("unmapped_source_columns", []),
                        "missing_target_columns": mapping_json.get("missing_target_columns", []),
                        "partitioning_recommendation": mapping_json.get("partitioning_recommendation"),
                        "naming_convention_suggestions": mapping_json.get("naming_convention_suggestions")
                    }
                else:
                    # Target selection returned null or target not found
                    res_json = {
                        "selected_target_id": None,
                        "confidence_score": confidence,
                        "reasoning": f"Selection Reason: {selection_reasoning}",
                        "column_mapping": None,
                        "unmapped_source_columns": [],
                        "missing_target_columns": [],
                        "partitioning_recommendation": None,
                        "naming_convention_suggestions": None
                    }

        confidence = float(res_json.get("confidence_score", 0.0))
        selected_target_id_str = res_json.get("selected_target_id")
        reasoning = res_json.get("reasoning", "No reasoning provided.")
        column_mapping = res_json.get("column_mapping")
        unmapped_source = res_json.get("unmapped_source_columns", [])
        missing_target = res_json.get("missing_target_columns", [])
        partitioning_rec = res_json.get("partitioning_recommendation")
        naming_suggestions = res_json.get("naming_convention_suggestions")

        requires_review = confidence < settings.INFERENCE_CONFIDENCE_THRESHOLD
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
                "requires_review": inference.requires_review
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
