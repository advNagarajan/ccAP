from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class TargetCatalogCreate(BaseModel):
    target_name: str
    target_type: str
    business_domain: str | None = None
    connection_details: dict
    schema_definition: dict | None = None
    is_system_generated: bool = False


class TargetCatalogCreateResponse(BaseModel):
    target_id: UUID
    target_name: str
    target_type: str
    target_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TargetCatalogResponse(BaseModel):
    target_id: UUID
    target_name: str
    target_type: str
    business_domain: str | None
    connection_details: dict
    schema_definition: dict | None
    target_status: str
    is_system_generated: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TargetCatalogUpdate(BaseModel):
    target_name: str | None = None
    target_type: str | None = None
    business_domain: str | None = None
    connection_details: dict | None = None
    schema_definition: dict | None = None
    target_status: str | None = None
    is_system_generated: bool | None = None
