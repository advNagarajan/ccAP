"""
An SQLAlchemy DB Model (metadata.data_quality_reports).
Used to store structured data quality reports with aggregate status, executed/failed counts, and rule-level results.
"""
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

class DataQualityReport(Base):
    __tablename__ = "data_quality_reports"
    __table_args__ = {"schema": "metadata"}

    report_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.jobs.job_id"),
        nullable=False
    )
    artifact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.artifact_records.artifact_id"),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50),  # 'PASSED', 'WARNING', 'FAILED'
        nullable=False
    )
    rules_executed: Mapped[int] = mapped_column(Integer, default=0)
    rules_failed: Mapped[int] = mapped_column(Integer, default=0)
    report_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    job = relationship("Job")
    artifact = relationship("ArtifactRecord")
