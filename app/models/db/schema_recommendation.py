"""
An SQLAlchemy DB Model (metadata.schema_recommendations).
Stores raw deterministic findings and AI-assisted recommendations.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, Text, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaRecommendation(Base):
    __tablename__ = "schema_recommendations"
    __table_args__ = {"schema": "metadata"}

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
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

    validation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.schema_validations.validation_id", ondelete="CASCADE"),
        nullable=False
    )

    drift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.schema_drifts.drift_id", ondelete="CASCADE"),
        nullable=False
    )

    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.target_catalog.target_id", ondelete="SET NULL"),
        nullable=True
    )

    recommendation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    deterministic_findings: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    recommendations_list: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    partitioning_recommendation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
