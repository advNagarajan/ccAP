import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
from datetime import datetime
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.target_catalog import TargetCatalog

# Create mock DB session
mock_db = MagicMock()

# Keep track of targets in an in-memory dictionary to mock listing and fetching
mock_targets_db = {}

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
        mock_targets_db[instance.target_id] = instance
        print(f"DEBUG mock_add: added target {instance.target_name} status={instance.target_status}")

mock_db.add = mock_add

def mock_get(model_class, ident):
    if model_class == TargetCatalog:
        if isinstance(ident, str):
            ident = uuid.UUID(ident)
        return mock_targets_db.get(ident)
    return None

mock_db.get = mock_get

def mock_execute(statement):
    result_mock = MagicMock()
    stmt_str = str(statement).lower()
    
    # Check if this is a query checking for target_name in WHERE clause
    if "target_name =" in stmt_str or "target_name=" in stmt_str:
        # Duplicate check query
        if mock_targets_db:
            existing = list(mock_targets_db.values())[0]
            result_mock.scalar_one_or_none.return_value = existing
        else:
            result_mock.scalar_one_or_none.return_value = None
    else:
        # Listing query
        active_targets = [t for t in mock_targets_db.values() if t.target_status == "ACTIVE"]
        result_mock.scalars.return_value.all.return_value = active_targets

    return result_mock

mock_db.execute = mock_execute

import pytest

# Override FastAPI get_db dependency
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


def test_target_catalog_api_workflow():
    created_target_id = None
    created_target_name = f"test_target_{uuid.uuid4().hex[:8]}"

    def print_test(name):
        print()
        print("=" * 60)
        print(name)
        print("=" * 60)

    print()
    print("#" * 80)
    print("TARGET CATALOG API INTEGRATION TEST SUITE")
    print("#" * 80)

    #
    # TEST 1 - CREATE TARGET
    #
    print_test("TEST 1 - CREATE TARGET")
    response = client.post(
        "/targets",
        json={
            "target_name": created_target_name,
            "target_type": "POSTGRESQL",
            "business_domain": "Customer",
            "connection_details": {
                "host": "localhost",
                "port": 5432,
                "database": "customer_db"
            },
            "schema_definition": {
                "fields": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "VARCHAR"}
                ]
            },
            "is_system_generated": False
        }
    )
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    body = response.json()
    created_target_id = body["target_id"]
    assert body["target_name"] == created_target_name
    assert body["target_type"] == "POSTGRESQL"
    assert body["target_status"] == "ACTIVE"
    print("PASS")

    #
    # TEST 2 - DUPLICATE TARGET
    #
    print_test("TEST 2 - DUPLICATE TARGET")
    response = client.post(
        "/targets",
        json={
            "target_name": created_target_name,
            "target_type": "POSTGRESQL",
            "connection_details": {}
        }
    )
    assert response.status_code == 409, f"Expected 409, got {response.status_code}: {response.text}"
    print("PASS")

    #
    # TEST 3 - INVALID TARGET TYPE
    #
    print_test("TEST 3 - INVALID TARGET TYPE")
    temp_db = mock_targets_db.copy()
    mock_targets_db.clear()

    response = client.post(
        "/targets",
        json={
            "target_name": f"invalid_type_{uuid.uuid4().hex[:8]}",
            "target_type": "INVALID_TYPE",
            "connection_details": {}
        }
    )
    assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
    mock_targets_db.update(temp_db)
    print("PASS")

    #
    # TEST 4 - GET ALL TARGETS
    #
    print_test("TEST 4 - GET ALL TARGETS")
    response = client.get("/targets")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    targets = response.json()
    assert len(targets) > 0
    assert any(t["target_id"] == created_target_id for t in targets)
    print("PASS")

    #
    # TEST 5 - GET TARGET BY ID
    #
    print_test("TEST 5 - GET TARGET BY ID")
    response = client.get(f"/targets/{created_target_id}")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    target = response.json()
    assert target["target_name"] == created_target_name
    assert target["target_status"] == "ACTIVE"
    print("PASS")

    #
    # TEST 6 - GET NONEXISTENT TARGET
    #
    print_test("TEST 6 - GET NONEXISTENT TARGET")
    response = client.get(f"/targets/{uuid.uuid4()}")
    assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    print("PASS")

    #
    # TEST 7 - PATCH TARGET
    #
    print_test("TEST 7 - PATCH TARGET")
    response = client.patch(
        f"/targets/{created_target_id}",
        json={
            "business_domain": "Customer Updated",
            "schema_definition": {
                "fields": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "VARCHAR"},
                    {"name": "email", "type": "VARCHAR"}
                ]
            }
        }
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["business_domain"] == "Customer Updated"
    assert len(body["schema_definition"]["fields"]) == 3
    print("PASS")

    #
    # TEST 8 - DELETE TARGET (DEACTIVATION)
    #
    print_test("TEST 8 - DELETE TARGET (DEACTIVATION)")
    response = client.delete(f"/targets/{created_target_id}")
    assert response.status_code == 204, f"Expected 204, got {response.status_code}: {response.text}"
    print("PASS")

    #
    # TEST 9 - DELETED TARGET HIDDEN FROM LIST
    #
    print_test("TEST 9 - DELETED TARGET HIDDEN FROM LIST")
    response = client.get("/targets")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    targets = response.json()
    assert not any(t["target_id"] == created_target_id for t in targets)
    print("PASS")

    #
    # TEST 10 - DELETED TARGET STILL RETRIEVABLE WITH INCLUDE_INACTIVE
    #
    print_test("TEST 10 - DELETED TARGET STILL RETRIEVABLE WITH INCLUDE_INACTIVE")
    response = client.get(f"/targets/{created_target_id}?include_inactive=true")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    body = response.json()
    assert body["target_status"] == "INACTIVE"
    print("PASS")

    print()
    print("#" * 80)
    print("ALL TARGET CATALOG API TESTS PASSED")
    print("#" * 80)
    print()
