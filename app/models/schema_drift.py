"""
An SQLAlchemy DB Model (metadata.schema_drift).
Used by the Validation worker to log anomalies against a target schema.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaDrift(Base):
    __tablename__ = "schema_drifts"
    __table_args__ = {"schema": "metadata"}

    drift_id: Mapped[uuid.UUID] = mapped_column(
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

    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.target_catalog.target_id", ondelete="SET NULL"),
        nullable=True
    )

    drift_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    drift_score: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )

    drift_summary: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
