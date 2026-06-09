from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class FeedbackCreate(BaseModel):
    target_id: UUID
    job_id: UUID
    observed_flattened_paths: list[str]
    user_action: str
    engineer_notes: str | None = None


class FeedbackResponse(BaseModel):
    feedback_id: UUID
    job_id: UUID
    target_id: UUID
    observed_flattened_paths: list[str]
    user_action: str
    engineer_notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True
