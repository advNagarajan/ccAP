from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class FallbackApproveRequest(BaseModel):
    approved_by: str | None = None
    review_notes: str | None = None


class FallbackRejectRequest(BaseModel):
    rejected_by: str | None = None
    review_notes: str | None = None


class FallbackResponse(BaseModel):
    request_id: UUID
    job_id: UUID
    artifact_id: UUID
    validation_id: UUID | None = None
    drift_id: UUID | None = None
    request_reason: str
    request_status: str
    backup_table_name: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    rejected_by: str | None = None
    rejected_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
