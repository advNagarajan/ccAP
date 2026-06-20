from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db.target_catalog import TargetCatalog
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.pubsub.publisher import publish_feedback_submitted

router = APIRouter(tags=["Feedback"])


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=201
)
def submit_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db)
):
    if payload.target_id is not None:
        target = db.get(TargetCatalog, payload.target_id)
        if target is None:
            raise HTTPException(
                status_code=404,
                detail="Target not found"
            )

    feedback = LlmFeedbackLoop(
        job_id=payload.job_id,
        target_id=payload.target_id,
        observed_flattened_paths=payload.observed_flattened_paths,
        user_action=payload.user_action,
        engineer_notes=payload.engineer_notes,
        stage=payload.stage,
        response_in_question=payload.response_in_question,
        user_id=payload.user_id
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Trigger async feedback loops processing if target is vectorized
    if feedback.target_id is not None:
        try:
            publish_feedback_submitted(
                job_id=feedback.job_id,
                target_id=feedback.target_id,
                user_action=feedback.user_action,
                notes=feedback.engineer_notes
            )
        except Exception as e:
            print(f"Error publishing feedback-submitted event: {e}")

    return feedback

