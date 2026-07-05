from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class SourceCreate(BaseModel):
    name: str
    source_type: str
    connection_details: dict
    description: str | None = None
    config_id: UUID

class SourceCreateResponse(BaseModel):
    source_id: UUID
    name: str
    source_type: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True
        
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

class SourceUpdate(BaseModel):
    name: str | None = None
    connection_details: dict | None = None
    description: str | None = None
    status: str | None = None
    config_id: UUID | None = None