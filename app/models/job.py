from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    text
)

from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"schema": "metadata"}

    job_id: Mapped[str] = mapped_column(
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

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("RECEIVED")
    )

    current_stage: Mapped[str | None] = mapped_column(
        String(100)
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime
    )

    error_message: Mapped[str | None] = mapped_column(
        Text
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    source = relationship(
        "Source"
    )