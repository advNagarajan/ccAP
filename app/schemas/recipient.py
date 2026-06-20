from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class RecipientCreate(BaseModel):
    email: str
    subscribed_topics: list[str] = Field(default_factory=list)


class RecipientUpdate(BaseModel):
    email: str | None = None
    is_active: bool | None = None
    subscribed_topics: list[str] | None = None


class RecipientResponse(BaseModel):
    recipient_id: UUID
    email: str
    is_active: bool
    subscribed_topics: list[str]
    created_at: datetime

    class Config:
        from_attributes = True
