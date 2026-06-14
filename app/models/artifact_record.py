"""
An SQLAlchemy DB Model (system.artifact_records).
Used by the pipeline to track files that have been processed to prevent duplication.
"""
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
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

from app.db.base import Base


class ArtifactRecord(Base):
    __tablename__ = "artifact_records"
    __table_args__ = {"schema": "metadata"}

    artifact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "metadata.sources.source_id"
        ),
        nullable=False
    )

    external_artifact_id: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    artifact_name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    artifact_metadata: Mapped[dict] = mapped_column(
        JSONB
    )

    discovered_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    failure_reason: Mapped[str | None] = mapped_column(Text)