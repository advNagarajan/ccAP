from datetime import datetime

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey
)

from sqlalchemy.dialects.postgresql import (
    UUID,
    JSONB
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.db.base import Base


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": "metadata"}

    source_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True
    )

    config_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "metadata.processing_configurations.config_id"
        ),
        nullable=False
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    connection_details: Mapped[dict] = mapped_column(
        JSONB
    )

    description: Mapped[str | None] = mapped_column(
        Text
    )

    status: Mapped[str] = mapped_column(
        String(30)
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime
    )

    configuration = relationship(
        "ProcessingConfiguration"
    )