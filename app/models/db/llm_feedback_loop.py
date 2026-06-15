"""
An SQLAlchemy DB Model (metadata.llm_feedback_loop).
Used by the Target Vectorizer to learn from human engineer overrides.
"""
from datetime import datetime

from sqlalchemy import (
    String,
    DateTime,
    Text,
    ForeignKey,
    func,
    text
)
from sqlalchemy.dialects.postgresql import (
    UUID,
    ARRAY
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.db.base import Base


class LlmFeedbackLoop(Base):
    __tablename__ = "llm_feedback_loop"
    __table_args__ = {"schema": "metadata"}

    feedback_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )

    job_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )

    target_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("metadata.target_catalog.target_id", ondelete="CASCADE"),
        nullable=False
    )

    observed_flattened_paths: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False
    )

    user_action: Mapped[str] = mapped_column(
        String(50),
        nullable=False
    )

    engineer_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )

    target = relationship("TargetCatalog")
