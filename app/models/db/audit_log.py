"""
An SQLAlchemy DB Model (metadata.audit_logs).
Tracks manual UI operations (triggers, retries, user modifications, approvals).
"""
import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, func, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = {"schema": "control_plane"}

    log_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    details: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )
