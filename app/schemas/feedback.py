from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    job_id: UUID
    target_id: UUID | None = None
    observed_flattened_paths: list[str] | None = None
    user_action: str | None = None
    engineer_notes: str | None = None
    stage: str | None = None
    response_in_question: str | None = None
    user_id: UUID | None = None


class FeedbackResponse(BaseModel):
    feedback_id: UUID
    job_id: UUID
    target_id: UUID | None = None
    observed_flattened_paths: list[str] | None = None
    user_action: str | None = None
    engineer_notes: str | None = None
    stage: str | None = None
    response_in_question: str | None = None
    user_id: UUID | None = None
    created_at: datetime

    class Config:
        from_attributes = True

