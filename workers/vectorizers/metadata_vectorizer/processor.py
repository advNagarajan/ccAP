import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.db.metadata_profile import MetadataProfile
from app.services.passport_service import get_vector_embedding
from app.services.metadata_service import generate_embedding_optimized_text
from app.pubsub.publisher import publish_metadata_vectorized
from app.services.job_stage_service import start_stage, complete_stage, fail_stage

logger = logging.getLogger("metadata_vectorizer")


async def sync_metadata_vector(
    job_id: str,
    artifact_id: str,
    metadata_profile_id: str,
    db: Session
) -> None:
    """
    Computes source_embedding for a MetadataProfile using Gemini API,
    saves it, and publishes to the metadata-vectorized topic.
    """
    profile_uuid = UUID(metadata_profile_id)
    job_uuid = UUID(job_id)
    logger.info(f"--- Processing Metadata Vector sync for metadata_profile_id={profile_uuid} ---")

    profile = db.get(MetadataProfile, profile_uuid)
    if profile is None:
        logger.error(f"MetadataProfile row not found for metadata_profile_id={profile_uuid}")
        return

    vector_stage = start_stage(job_uuid, "Metadata Vectorization", db)

    try:
        # Fallback check if embedding_optimized_text was not computed during ingestion stage
        if not profile.embedding_optimized_text:
            logger.warning(f"embedding_optimized_text missing for profile={profile_uuid}. Generating it now.")
            profile.embedding_optimized_text = generate_embedding_optimized_text(profile.metadata_json)

        logger.info(f"Requesting vector embedding for metadata profile (length={len(profile.embedding_optimized_text)} chars).")
        embedding = await get_vector_embedding(profile.embedding_optimized_text)

        logger.info(f"Saving source_embedding vector to metadata_profile_id={profile_uuid}.")
        profile.source_embedding = embedding
        db.commit()

        logger.info(f"Publishing metadata-vectorized event for job_id={job_id}, artifact_id={artifact_id}")
        publish_metadata_vectorized(
            job_id=job_id,
            artifact_id=artifact_id,
            metadata_profile_id=metadata_profile_id
        )
        
        complete_stage(vector_stage.stage_history_id, db)
        logger.info(f"Successfully processed metadata vector sync for metadata_profile_id={profile_uuid}.")
    except Exception as e:
        logger.error(f"Failed to process metadata vector sync for metadata_profile_id={profile_uuid}: {e}", exc_info=True)
        db.rollback()
        try:
            fail_stage(vector_stage.stage_history_id, e, db)
        except Exception:
            pass
        raise
