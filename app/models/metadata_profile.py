from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MetadataProfile(Base):
    __tablename__ = "metadata_profiles"
    __table_args__ = {"schema": "metadata"}

    metadata_profile_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4
    )

    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "metadata.jobs.job_id"
        ),
        nullable=False
    )

    artifact_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "metadata.artifact_records.artifact_id"
        ),
        nullable=False
    )

    metadata_json: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )