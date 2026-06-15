"""
An SQLAlchemy DB Model (metadata.target_catalog).
Used by Vectorizers and Inference as the definitive registry of destination tables.
"""
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    Boolean,
    Text,
    func,
    text
)
from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column
)
from pgvector.sqlalchemy import Vector

from app.db.base import Base


class TargetCatalog(Base):
    __tablename__ = "target_catalog"
    __table_args__ = {"schema": "metadata"}

    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    target_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    target_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    business_domain: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    connection_details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    schema_definition: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    target_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default="ACTIVE"
    )

    is_system_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="FALSE"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    target_passport_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    target_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768),
        nullable=True
    )
