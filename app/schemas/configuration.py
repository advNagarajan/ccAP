from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConfigurationCreateResponse(BaseModel):
    config_id: UUID
    filename: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConfigurationResponse(BaseModel):
    config_id: UUID

    name: str

    description: str | None

    config_type: str

    config_subtype: str | None

    config_content: dict

    status: str

    version: int

    created_at: datetime

    updated_at: datetime

    class Config:
        from_attributes = True


class ConfigurationUpdate(BaseModel):
    description: str | None = None

    config_content: dict | None = None

    status: str | None = None

    version: int | None = None