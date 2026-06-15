import logging
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.db.target_catalog import TargetCatalog
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.services.passport_service import (
    generate_target_passport_text,
    get_vector_embedding
)

logger = logging.getLogger("target_vectorizer")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


async def sync_target_vector_on_mutation(target_id: str, db: Session) -> None:
    """
    Compiles passport text and generates vector embedding for a target catalog item.
    """
    target_uuid = UUID(target_id)
    logger.info(f"--- Processing Target Mutation vector generation for target_id={target_uuid} ---")
    
    target = db.get(TargetCatalog, target_uuid)
    if target is None:
        logger.error(f"Target catalog row not found for target_id={target_uuid}")
        return

    try:
        # Fetch historical feedback loops to append to passport if any exist
        feedback_logs = db.scalars(
            select(LlmFeedbackLoop)
            .where(LlmFeedbackLoop.target_id == target_uuid)
            .order_by(LlmFeedbackLoop.created_at.desc())
        ).all()

        logger.info(f"Compiling target passport for '{target.target_name}' using {len(feedback_logs)} feedback records.")
        passport_text = generate_target_passport_text(target, list(feedback_logs))

        logger.info(f"Requesting vector embedding for target passport (length={len(passport_text)} chars).")
        embedding = await get_vector_embedding(passport_text)

        logger.info(f"Saving compiled passport text and embedding vector back to target_id={target_uuid}.")
        target.target_passport_text = passport_text
        target.target_embedding = embedding
        db.commit()
        logger.info(f"Successfully generated target vector for target_id={target_uuid}.")
    except Exception as e:
        logger.error(f"Failed to generate target vector for target_id={target_uuid}: {e}", exc_info=True)
        db.rollback()
        raise


async def append_feedback_and_revectorize(
    job_id: str,
    target_id: str,
    user_action: str,
    notes: str,
    db: Session
) -> None:
    """
    Refetches all feedback loop records relative to a target catalog item,
    generates a revised passport, creates a revised embedding, and updates the target row.
    """
    target_uuid = UUID(target_id)
    job_uuid = UUID(job_id)
    logger.info(f"--- Running Feedback Revectorization for target_id={target_uuid} from job_id={job_uuid} ---")

    target = db.get(TargetCatalog, target_uuid)
    if target is None:
        logger.error(f"Target catalog row not found for target_id={target_uuid}")
        return

    try:
        # Fetch all feedback loops linked to this target_id
        feedback_logs = db.scalars(
            select(LlmFeedbackLoop)
            .where(LlmFeedbackLoop.target_id == target_uuid)
            .order_by(LlmFeedbackLoop.created_at.desc())
        ).all()

        logger.info(f"Feedback loop list size is {len(feedback_logs)}. Generating updated passport text.")
        passport_text = generate_target_passport_text(target, list(feedback_logs))

        logger.info("Requesting updated vector embedding.")
        embedding = await get_vector_embedding(passport_text)

        logger.info(f"Updating target_catalog target_id={target_uuid} with new feedback-aware vector.")
        target.target_passport_text = passport_text
        target.target_embedding = embedding
        db.commit()
        logger.info(f"Successfully updated feedback-based vector for target_id={target_uuid}.")
    except Exception as e:
        logger.error(f"Failed to update feedback-based vector for target_id={target_uuid}: {e}", exc_info=True)
        db.rollback()
        raise
