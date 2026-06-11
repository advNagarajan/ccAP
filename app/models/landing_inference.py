import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, Text, Numeric, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LandingInference(Base):
    __tablename__ = "landing_inferences"
    __table_args__ = {"schema": "metadata"}

    inference_id: Mapped[uuid.UUID] = mapped_column(
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

    metadata_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.metadata_profiles.metadata_profile_id", ondelete="CASCADE"),
        nullable=False
    )

    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.target_catalog.target_id", ondelete="SET NULL"),
        nullable=True
    )

    confidence_score: Mapped[float] = mapped_column(
        Numeric(5, 4),
        nullable=False
    )

    column_mapping: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    unmapped_source_columns: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    missing_target_columns: Mapped[list[str] | None] = mapped_column(
        JSONB,
        nullable=True
    )

    reasoning: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    requires_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
