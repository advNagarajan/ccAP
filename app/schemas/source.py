from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class SourceResponse(BaseModel):
    source_id: UUID
    name: str
    source_type: str
    connection_details: dict
    description: str | None
    config_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True