from datetime import datetime
from uuid import UUID as UUIDType

from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    text,
    func
)

from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from app.db.base import Base


class ProcessingConfiguration(Base):
    __tablename__ = "processing_configurations"
    __table_args__ = {"schema": "metadata"}

    config_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(Text)

    config_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    config_subtype: Mapped[str | None] = mapped_column(String(50))

    config_content: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="ACTIVE"
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("1")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
    )