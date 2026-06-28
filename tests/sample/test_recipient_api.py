import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.notification_recipient import NotificationRecipient

# Create mock DB session
mock_db = MagicMock()

# Keep track of recipients in an in-memory dictionary to mock listing and fetching
mock_recipients_db = {}

def mock_add(instance):
    if isinstance(instance, NotificationRecipient):
        if not getattr(instance, "recipient_id", None):
            instance.recipient_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        mock_recipients_db[instance.recipient_id] = instance

mock_db.add = mock_add

def mock_get(model_class, ident):
    if model_class == NotificationRecipient:
        if isinstance(ident, str):
            ident = uuid.UUID(ident)
        return mock_recipients_db.get(ident)
    return None

mock_db.get = mock_get

def mock_execute(statement):
    result_mock = MagicMock()
    stmt_str = str(statement).lower()
    
    # Check if this is a query checking for email in WHERE clause
    if "email =" in stmt_str or "email=" in stmt_str:
        try:
            params = statement.compile().params
            email_val = params.get("email_1")
            existing = None
            if email_val:
                for r in mock_recipients_db.values():
                    if r.email == email_val:
                        existing = r
                        break
            result_mock.scalar_one_or_none.return_value = existing
        except Exception:
            result_mock.scalar_one_or_none.return_value = None
    else:
        # Listing query
        result_mock.scalars.return_value.all.return_value = list(mock_recipients_db.values())

    return result_mock

mock_db.execute = mock_execute

def mock_delete(instance):
    if isinstance(instance, NotificationRecipient):
        if instance.recipient_id in mock_recipients_db:
            del mock_recipients_db[instance.recipient_id]

mock_db.delete = mock_delete

def override_get_db():
    try:
        yield mock_db
    finally:
        pass

@pytest.fixture(autouse=True)
def setup_db_override():
    app.dependency_overrides[get_db] = override_get_db
    yield
    if get_db in app.dependency_overrides:
        del app.dependency_overrides[get_db]

client = TestClient(app)

def test_create_recipient_api():
    mock_recipients_db.clear()
    email = f"test_{uuid.uuid4().hex[:8]}@company.com"
    response = client.post(
        "/recipients",
        json={
            "email": email,
            "subscribed_topics": ["job-failed", "job-completed"]
        }
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["subscribed_topics"] == ["job-failed", "job-completed"]
    assert body["is_active"] is True

def test_get_recipients_api():
    mock_recipients_db.clear()
    rec_id = uuid.uuid4()
    rec = NotificationRecipient(
        recipient_id=rec_id,
        email="test@company.com",
        is_active=True,
        subscribed_topics=["job-failed"],
        created_at=datetime.utcnow()
    )
    mock_recipients_db[rec_id] = rec

    response = client.get("/recipients")
    assert response.status_code == 200
    body = response.json()
    assert len(body) > 0
    assert body[0]["email"] == "test@company.com"
