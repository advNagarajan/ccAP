import uuid
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

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
response = client.post(
    "/targets",
    json={
        "target_name": f"invalid_type_{uuid.uuid4().hex[:8]}",
        "target_type": "INVALID_TYPE",
        "connection_details": {}
    }
)
assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
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
