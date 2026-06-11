import json
import logging
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.models.metadata_profile import MetadataProfile
from app.models.target_catalog import TargetCatalog
from app.models.landing_inference import LandingInference
from app.services.metadata_service import (
    generate_llm_optimized_json,
    generate_target_llm_optimized_json
)
from app.services.llm import get_llm_provider
from app.services.job_stage_service import start_stage, complete_stage, fail_stage
from app.pubsub.publisher import publish_target_inferred

logger = logging.getLogger("landing_inference")


class InferenceResponseSchema(BaseModel):
    selected_target_id: str | None = Field(
        default=None,
        description="The UUID string of the selected target database table, or null if no candidate is sufficiently compatible."
    )
    confidence_score: float = Field(
        description="A value between 0.0 and 1.0 reflecting actual confidence in this selection."
    )
    reasoning: str = Field(
        description="Concise rationale for audit/debugging explaining choice, major schema/datatype compatibility concerns, or coverage gaps."
    )
    column_mapping: dict[str, str | None] | None = Field(
        default=None,
        description="Dictionary mapping each source column name to the matching target column name (or null if unmatched)."
    )
    unmapped_source_columns: list[str] = Field(
        default_factory=list,
        description="List of source column names that could not be mapped to any target column."
    )
    missing_target_columns: list[str] = Field(
        default_factory=list,
        description="List of target column names that are missing from the source dataset schema."
    )


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

    if not profile.source_embedding:
        logger.error(f"MetadataProfile has no embedding vectorized yet: {profile_uuid}")
        return

    # 1. Start the target inference audit stage
    stage = start_stage(job_uuid, "Target Inference", db)

    try:
        # 2. Retrieve Top 20 Candidates using pgvector cosine similarity
        distance_expr = TargetCatalog.target_embedding.cosine_distance(profile.source_embedding)
        stmt = (
            select(TargetCatalog, (1.0 - distance_expr).label("similarity"))
            .where(TargetCatalog.target_embedding.is_not(None))
            .order_by(distance_expr)
            .limit(20)
        )
        
        results = db.execute(stmt).all()
        logger.info(f"Retrieved {len(results)} candidate targets from TargetCatalog.")

        # 3. Format context for prompt
        source_json = generate_llm_optimized_json(profile.metadata_json)
        
        candidates_context = []
        for idx, (target, similarity) in enumerate(results, 1):
            target_json = generate_target_llm_optimized_json(target)
            candidates_context.append(
                f"Candidate {idx}\n"
                f"Similarity: {similarity:.4f}\n"
                f"Target ID: {target.target_id}\n"
                f"Target Name: {target.target_name}\n"
                f"Business Domain: {target.business_domain or 'General'}\n"
                f"Description: {target.description or 'No description'}\n"
                f"Schema Fields:\n{json.dumps(target_json['fields'], indent=2)}\n"
                f"----------------------------------------"
            )

        candidates_str = "\n".join(candidates_context)
        
        prompt = (
            "Analyze the incoming source dataset's metadata schema and determine "
            "which of the provided candidate database tables is the best target landing zone for it.\n\n"
            "Incoming Source Dataset Schema:\n"
            f"{json.dumps(source_json, indent=2)}\n\n"
            "Candidate Target Databases (Top 20 Retrived via Semantic Search):\n"
            f"{candidates_str}\n\n"
            "Instructions:\n"
            "1. Evaluate candidates using the following priority order:\n"
            "   - Business meaning and semantic purpose of the dataset.\n"
            "   - Column name alignment.\n"
            "   - Schema coverage (percentage of source columns that can be mapped).\n"
            "   - Data type compatibility.\n"
            "   - Retrieval similarity score.\n"
            "   - Candidate descriptions and domain metadata.\n\n"
            "2. Retrieval-Awareness context:\n"
            "   - Candidates were pre-selected using vector similarity search.\n"
            "   - The correct target, if it exists, is likely among the provided candidates.\n"
            "   - Similarity scores should be considered as supporting evidence, not as the sole decision factor.\n\n"
            "3. Schema Coverage Analysis:\n"
            "   - Determine how many source columns can be mapped. Prefer candidates with higher mapping coverage.\n"
            "   - Identify unmapped source fields and missing target fields.\n\n"
            "4. Reasoning Requirements (intended for audit/debugging only, keep concise):\n"
            "   - Explain why the selected target was chosen.\n"
            "   - Highlight any major schema compatibility concerns, major datatype compatibility concerns, or significant coverage gaps.\n"
            "   - Do NOT perform extensive runner-up comparison or detailed rejection analysis for every candidate.\n\n"
            "5. No-Match Handling:\n"
            "   - If no candidate is sufficiently compatible, return selected_target_id = null, column_mapping = null, and explain why in reasoning.\n"
            "   - The confidence_score should reflect your actual certainty in this assessment.\n\n"
            "6. Your response MUST be valid JSON adhering exactly to the schema."
        )

        # 4. Invoke LLM Provider
        llm_provider = get_llm_provider()
        logger.info("Sending prompt to generative LLM provider.")
        response_text = await llm_provider.generate_response(
            prompt=prompt,
            response_schema=InferenceResponseSchema
        )
        
        # Parse output
        res_json = json.loads(response_text)
        confidence = float(res_json.get("confidence_score", 0.0))
        selected_target_id_str = res_json.get("selected_target_id")
        reasoning = res_json.get("reasoning", "No reasoning provided.")
        column_mapping = res_json.get("column_mapping")
        unmapped_source = res_json.get("unmapped_source_columns", [])
        missing_target = res_json.get("missing_target_columns", [])
        
        requires_review = confidence < settings.INFERENCE_CONFIDENCE_THRESHOLD
        
        target_uuid = UUID(selected_target_id_str) if selected_target_id_str else None
        
        # 5. Store result in dedicated landing_inferences table
        inference = LandingInference(
            job_id=job_uuid,
            artifact_id=profile.artifact_id,
            metadata_profile_id=profile_uuid,
            target_id=target_uuid,
            confidence_score=confidence,
            column_mapping=column_mapping,
            unmapped_source_columns=unmapped_source,
            missing_target_columns=missing_target,
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
