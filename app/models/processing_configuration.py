from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessingConfiguration(Base):
    __tablename__ = "processing_configurations"
    __table_args__ = {"schema": "metadata"}

    config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    config_content: Mapped[dict] = mapped_column(JSONB)

    status: Mapped[str] = mapped_column(String(30))

    version: Mapped[int] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime)

    updated_at: Mapped[datetime] = mapped_column(DateTime)