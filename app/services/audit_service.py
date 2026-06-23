from sqlalchemy.orm import Session
from app.models.db.audit_log import AuditLog


def create_audit_entry(db: Session, user_email: str, action: str, details: dict | None = None) -> AuditLog:
    """
    Creates and persists an audit log entry in the database.
    """
    entry = AuditLog(
        user_email=user_email,
        action=action,
        details=details
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
