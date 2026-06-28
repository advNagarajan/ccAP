import time
import uuid
import requests

BASE_URL = "http://127.0.0.1:8000"

created_config_id = None
created_filename = None


def assert_status(response, expected):

    if response.status_code != expected:

        print()
        print("EXPECTED:", expected)
        print("ACTUAL:", response.status_code)

        try:
            print(response.json())

        except Exception:
            print(response.text)

        raise AssertionError(
            f"Expected {expected}, got {response.status_code}"
        )


def upload(path, filename=None):

    if filename is None:
        filename = f"{uuid.uuid4()}.yaml"

    with open(path, "rb") as f:

        response = requests.post(
            f"{BASE_URL}/configurations",
            files={
                "file": (
                    filename,
                    f,
                    "application/x-yaml"
                )
            }
        )

    return response


def print_test(name):

    print()
    print("=" * 60)
    print(name)
    print("=" * 60)


print()
print("#" * 80)
print("CONFIGURATION API INTEGRATION TEST SUITE")
print("#" * 80)

#
# TEST 1
#

print_test(
    "TEST 1 - CREATE CONFIGURATION"
)

created_filename = (
    f"{uuid.uuid4()}.yaml"
)

response = upload(
    "tests/data/valid_source.yaml",
    created_filename
)

assert_status(
    response,
    201
)

body = response.json()

created_config_id = body["config_id"]

assert body["status"] == "ACTIVE"

print("PASS")

#
# TEST 2
#

print_test(
    "TEST 2 - DUPLICATE CONFIGURATION"
)

response = upload(
    "tests/data/valid_source.yaml",
    created_filename
)

assert_status(
    response,
    409
)

print("PASS")

#
# TEST 3
#

print_test(
    "TEST 3 - INVALID CONFIG TYPE"
)

response = upload(
    "tests/data/invalid_type.yaml"
)

assert_status(
    response,
    400
)

print("PASS")

#
# TEST 4
#

print_test(
    "TEST 4 - INVALID CONFIG SUBTYPE"
)

response = upload(
    "tests/data/invalid_subtype.yaml"
)

assert_status(
    response,
    400
)

print("PASS")

#
# TEST 5
#

print_test(
    "TEST 5 - INVALID YAML"
)

response = upload(
    "tests/data/invalid_yaml.yaml"
)

assert_status(
    response,
    400
)

print("PASS")

#
# TEST 6
#

print_test(
    "TEST 6 - GET ALL CONFIGURATIONS"
)

response = requests.get(
    f"{BASE_URL}/configurations"
)

assert_status(
    response,
    200
)

configs = response.json()

assert len(configs) > 0

print("PASS")

#
# TEST 7
#

print_test(
    "TEST 7 - GET CONFIGURATION BY ID"
)

response = requests.get(
    f"{BASE_URL}/configurations/{created_config_id}"
)

assert_status(
    response,
    200
)

config = response.json()

assert (
    config["config_id"]
    == created_config_id
)

assert (
    config["status"]
    == "ACTIVE"
)

print("PASS")

#
# TEST 8
#

print_test(
    "TEST 8 - GET NONEXISTENT CONFIGURATION"
)

response = requests.get(
    f"{BASE_URL}/configurations/00000000-0000-0000-0000-000000000000"
)

assert_status(
    response,
    404
)

print("PASS")

#
# TEST 9
#

print_test(
    "TEST 9 - PATCH DESCRIPTION"
)

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "description":
            "updated by integration suite"
    }
)

assert_status(
    response,
    200
)

body = response.json()

assert (
    body["description"]
    == "updated by integration suite"
)

assert (
    body["version"]
    == 2
)

print("PASS")

#
# TEST 10
#

print_test(
    "TEST 10 - PATCH STATUS"
)

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "status":
            "INACTIVE"
    }
)

assert_status(
    response,
    200
)

body = response.json()

assert (
    body["status"]
    == "INACTIVE"
)

assert (
    body["version"]
    == 3
)

print("PASS")

#
# TEST 11
#

print_test(
    "TEST 11 - INVALID STATUS"
)

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "status":
            "RANDOM_STATUS"
    }
)

assert_status(
    response,
    400
)

print("PASS")

#
# TEST 12
#

print_test(
    "TEST 12 - MULTIPLE VERSION INCREMENTS"
)

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "description":
            "version 4"
    }
)

assert_status(
    response,
    200
)

assert response.json()["version"] == 4

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "description":
            "version 5"
    }
)

assert_status(
    response,
    200
)

assert response.json()["version"] == 5

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "description":
            "version 6"
    }
)

assert_status(
    response,
    200
)

assert response.json()["version"] == 6

print("PASS")

#
# TEST 13
#

print_test(
    "TEST 13 - UPDATED_AT CHANGES"
)

response = requests.get(
    f"{BASE_URL}/configurations/{created_config_id}"
)

assert_status(
    response,
    200
)

before = response.json()["updated_at"]

time.sleep(2)

response = requests.patch(
    f"{BASE_URL}/configurations/{created_config_id}",
    json={
        "description":
            "updated timestamp check"
    }
)

assert_status(
    response,
    200
)

after = response.json()["updated_at"]

assert before != after

print("PASS")

#
# TEST 14
#

print_test(
    "TEST 14 - SOFT DELETE"
)

response = requests.delete(
    f"{BASE_URL}/configurations/{created_config_id}"
)

assert_status(
    response,
    200
)

body = response.json()

assert (
    body["status"]
    == "DELETED"
)

assert (
    body["version"]
    == 8
)

print("PASS")

#
# TEST 15
#

print_test(
    "TEST 15 - DELETED CONFIGURATION HIDDEN FROM LIST"
)

response = requests.get(
    f"{BASE_URL}/configurations"
)

assert_status(
    response,
    200
)

configs = response.json()

config_ids = [
    c["config_id"]
    for c in configs
]

assert (
    created_config_id
    not in config_ids
)

print("PASS")

#
# TEST 16
#

print_test(
    "TEST 16 - DELETED CONFIGURATION STILL RETRIEVABLE"
)

response = requests.get(
    f"{BASE_URL}/configurations/{created_config_id}"
)

assert_status(
    response,
    200
)

body = response.json()

assert (
    body["status"]
    == "DELETED"
)

print("PASS")

print()
print("#" * 80)
print("ALL CONFIGURATION API TESTS PASSED")
print("#" * 80)
print()