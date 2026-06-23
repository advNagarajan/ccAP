"""
An SQLAlchemy DB Model (metadata.users).
Represents users in the platform.
"""
from datetime import datetime
import uuid

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "control_plane"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    email: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    hashed_password: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="USER",
        default="USER"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now()
    )
