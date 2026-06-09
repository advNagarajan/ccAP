import uuid
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.target_catalog import TargetCatalog
from app.models.llm_feedback_loop import LlmFeedbackLoop
from workers.vector_sync.processor import (
    sync_target_vector_on_mutation,
    append_feedback_and_revectorize
)

# Create mock DB session
mock_db = MagicMock()

def mock_add(instance):
    if isinstance(instance, TargetCatalog):
        if not getattr(instance, "target_id", None):
            instance.target_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        if not getattr(instance, "updated_at", None):
            instance.updated_at = datetime.utcnow()
        if not getattr(instance, "target_status", None):
            instance.target_status = "ACTIVE"
    elif isinstance(instance, LlmFeedbackLoop):
        if not getattr(instance, "feedback_id", None):
            instance.feedback_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()

mock_db.add = mock_add

# Override FastAPI get_db dependency
def override_get_db():
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def print_test(name):
    print()
    print("=" * 60)
    print(name)
    print("=" * 60)


print()
print("#" * 80)
print("VECTOR SYNC & FEEDBACK LOOP MOCKED INTEGRATION TEST SUITE")
print("#" * 80)

#
# TEST 1 - POST TARGET & PROCESS MUTATION
#
print_test("TEST 1 - POST TARGET & PROCESS MUTATION")
target_name = f"vector_target_{uuid.uuid4().hex[:8]}"

# Configure mock DB behavior for POST /targets
mock_db.execute.return_value.scalar_one_or_none.return_value = None  # No duplicate target exists

response = client.post(
    "/targets",
    json={
        "target_name": target_name,
        "target_type": "POSTGRESQL",
        "business_domain": "Finance",
        "description": "Financial ledger transactions landing zone",
        "connection_details": {
            "host": "postgres-db",
            "port": 5432,
            "database": "finance"
        },
        "schema_definition": {
            "fields": [
                {"name": "tx_id", "type": "UUID", "primary_key": True},
                {"name": "amount", "type": "DECIMAL", "nullable": False},
                {"name": "currency", "type": "VARCHAR"}
            ]
        },
        "is_system_generated": False
    }
)
assert response.status_code == 201, f"POST failed: {response.text}"
target_data = response.json()
target_id = target_data["target_id"]

# Set up mock target instance for processor
mock_target = TargetCatalog(
    target_id=uuid.UUID(target_id),
    target_name=target_name,
    target_type="POSTGRESQL",
    business_domain="Finance",
    description="Financial ledger transactions landing zone",
    connection_details={"host": "postgres-db", "port": 5432, "database": "finance"},
    schema_definition={
        "fields": [
            {"name": "tx_id", "type": "UUID", "primary_key": True},
            {"name": "amount", "type": "DECIMAL", "nullable": False},
            {"name": "currency", "type": "VARCHAR"}
        ]
    },
    is_system_generated=False,
    target_status="ACTIVE",
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow()
)

mock_db.get.return_value = mock_target
mock_db.scalars.return_value.all.return_value = []  # No feedback logs initially

mock_vector = [0.01] * 768
with patch("workers.vector_sync.processor.get_vector_embedding", new_callable=AsyncMock) as mock_embed:
    mock_embed.return_value = mock_vector

    # Execute mutation processing worker
    asyncio_run = pytest.importorskip("asyncio").run
    asyncio_run(sync_target_vector_on_mutation(target_id, mock_db))

    # Assertions
    assert mock_target.target_passport_text is not None
    assert "Financial ledger transactions landing zone" in mock_target.target_passport_text
    assert "Tx Id" in mock_target.target_passport_text
    assert "(unique identifier)" in mock_target.target_passport_text
    assert "Amount" in mock_target.target_passport_text
    assert "(present in 100% of records)" in mock_target.target_passport_text
    assert mock_target.target_embedding == mock_vector
    print("PASS")


#
# TEST 2 - SUBMIT FEEDBACK & PROCESS RE-VECTORIZATION
#
print_test("TEST 2 - SUBMIT FEEDBACK & PROCESS RE-VECTORIZATION")

job_id = str(uuid.uuid4())
mock_db.get.return_value = mock_target  # Ensure target is found when adding feedback

response = client.post(
    "/feedback",
    json={
        "target_id": target_id,
        "job_id": job_id,
        "observed_flattened_paths": ["tx_id", "amount"],
        "user_action": "ROUTE_TO_MISC",
        "engineer_notes": "Routing currency errors to misc ledger"
    }
)
assert response.status_code == 201, f"Feedback POST failed: {response.text}"
feedback_data = response.json()
assert feedback_data["user_action"] == "ROUTE_TO_MISC"
assert feedback_data["engineer_notes"] == "Routing currency errors to misc ledger"

# Set up mock feedback log list
mock_feedback = LlmFeedbackLoop(
    feedback_id=uuid.UUID(feedback_data["feedback_id"]),
    job_id=uuid.UUID(job_id),
    target_id=uuid.UUID(target_id),
    observed_flattened_paths=["tx_id", "amount"],
    user_action="ROUTE_TO_MISC",
    engineer_notes="Routing currency errors to misc ledger"
)
mock_db.scalars.return_value.all.return_value = [mock_feedback]

mock_vector = [0.02] * 768
with patch("workers.vector_sync.processor.get_vector_embedding", new_callable=AsyncMock) as mock_embed:
    mock_embed.return_value = mock_vector

    # Execute feedback loop processing worker
    asyncio_run(
        append_feedback_and_revectorize(
            job_id=job_id,
            target_id=target_id,
            user_action="ROUTE_TO_MISC",
            notes="Routing currency errors to misc ledger",
            db=mock_db
        )
    )

    # Assertions
    assert "Historical Human Engineering Feedback Guidelines:" in mock_target.target_passport_text
    assert "ROUTE_TO_MISC" in mock_target.target_passport_text
    assert "Routing currency errors to misc ledger" in mock_target.target_passport_text
    assert mock_target.target_embedding == mock_vector
    print("PASS")

print()
print("#" * 80)
print("ALL MOCKED VECTOR SYNC & FEEDBACK LOOP TESTS PASSED")
print("#" * 80)
print()
