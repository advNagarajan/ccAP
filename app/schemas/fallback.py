from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class DatabaseConnectionDetails(BaseModel):
    db_type: str = "postgresql"
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


class FallbackApproveRequest(BaseModel):
    approved_by: str | None = None
    review_notes: str | None = None
    schema_name: str | None = "raw_landing"
    table_name: str | None = None
    connection_details: DatabaseConnectionDetails | None = None


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
    generated_ddl: str | None = None

    class Config:
        from_attributes = True
