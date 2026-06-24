from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IngestionCreate(BaseModel):
    source_id: UUID
    force_dq: bool = False


class IngestionResponse(BaseModel):
    job_id: UUID
    source_id: UUID
    status: str
    current_stage: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True