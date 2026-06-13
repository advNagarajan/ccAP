import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaFallbackRequest(Base):
    __tablename__ = "schema_fallback_requests"
    __table_args__ = {"schema": "metadata"}

    request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.jobs.job_id", ondelete="CASCADE"),
        nullable=False
    )

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.artifact_records.artifact_id", ondelete="CASCADE"),
        nullable=False
    )

    validation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.schema_validations.validation_id", ondelete="SET NULL"),
        nullable=True
    )

    drift_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.schema_drifts.drift_id", ondelete="SET NULL"),
        nullable=True
    )

    request_reason: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    request_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING"
    )

    backup_table_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    approved_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    rejected_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )

    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    review_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
