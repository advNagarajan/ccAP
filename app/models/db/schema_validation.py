"""
An SQLAlchemy DB Model (metadata.schema_validations).
Used by the Validation worker to store the overall health score of an inference mapping.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func, Numeric, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SchemaValidation(Base):
    __tablename__ = "schema_validations"
    __table_args__ = {"schema": "metadata"}

    validation_id: Mapped[uuid.UUID] = mapped_column(
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

    inference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.landing_inferences.inference_id", ondelete="CASCADE"),
        nullable=False
    )

    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.target_catalog.target_id", ondelete="SET NULL"),
        nullable=True
    )

    validation_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    coverage_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )

    target_match_percentage: Mapped[float] = mapped_column(
        Numeric(5, 2),
        nullable=False
    )

    mapped_column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    source_column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    target_column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    report_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
