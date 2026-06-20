import uuid
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db.notification_recipient import NotificationRecipient
from app.schemas.recipient import RecipientCreate, RecipientUpdate, RecipientResponse

router = APIRouter(
    tags=["Notification Recipients"]
)

@router.post("/recipients", response_model=RecipientResponse, status_code=status.HTTP_201_CREATED)
def create_recipient(payload: RecipientCreate, db: Session = Depends(get_db)):
    existing = db.execute(
        select(NotificationRecipient).where(NotificationRecipient.email == payload.email)
    ).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recipient with this email already exists"
        )

    recipient = NotificationRecipient(
        recipient_id=uuid.uuid4(),
        email=payload.email,
        subscribed_topics=payload.subscribed_topics,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    return recipient

@router.get("/recipients", response_model=list[RecipientResponse])
def get_recipients(db: Session = Depends(get_db)):
    recipients = db.execute(
        select(NotificationRecipient)
    ).scalars().all()
    return recipients

@router.get("/recipients/{recipient_id}", response_model=RecipientResponse)
def get_recipient(recipient_id: UUID, db: Session = Depends(get_db)):
    recipient = db.get(NotificationRecipient, recipient_id)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found"
        )
    return recipient

@router.patch("/recipients/{recipient_id}", response_model=RecipientResponse)
def update_recipient(recipient_id: UUID, payload: RecipientUpdate, db: Session = Depends(get_db)):
    recipient = db.get(NotificationRecipient, recipient_id)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found"
        )

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(recipient, field, value)

    db.commit()
    db.refresh(recipient)
    return recipient

@router.delete("/recipients/{recipient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_recipient(recipient_id: UUID, db: Session = Depends(get_db)):
    recipient = db.get(NotificationRecipient, recipient_id)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient not found"
        )
    db.delete(recipient)
    db.commit()
    return
