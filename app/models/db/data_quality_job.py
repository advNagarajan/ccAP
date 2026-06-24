"""
An SQLAlchemy DB Model (metadata.data_quality_jobs).
Used to map quality check execution runs 1-to-1 with independent entries in metadata.jobs.
"""
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class DataQualityJob(Base):
    __tablename__ = "data_quality_jobs"
    __table_args__ = {"schema": "metadata"}

    quality_job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.jobs.job_id", ondelete="CASCADE"),
        primary_key=True
    )
    parent_job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.jobs.job_id"),
        nullable=False
    )
    artifact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.artifact_records.artifact_id"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    job = relationship("Job", foreign_keys=[quality_job_id])
    parent_job = relationship("Job", foreign_keys=[parent_job_id])
    artifact = relationship("ArtifactRecord")
