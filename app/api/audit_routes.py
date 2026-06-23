from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel

from app.db.session import get_db
from app.models.db.audit_log import AuditLog
from app.api.dependencies import get_current_user
from app.models.db.user import User

router = APIRouter(tags=["Audit Logs"])


class AuditLogResponse(BaseModel):
    log_id: UUID
    user_email: str
    action: str
    details: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


@router.get(
    "/audit-logs",
    response_model=List[AuditLogResponse]
)
def get_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves all audit logs in the system, sorted descending by timestamp.
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    result = db.execute(stmt)
    return result.scalars().all()
