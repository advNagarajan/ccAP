import uuid
import requests

BASE_URL = "http://127.0.0.1:8000"

created_source_id = None


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


def print_test(name):

    print()
    print("=" * 60)
    print(name)
    print("=" * 60)


print()
print("#" * 80)
print("INGESTION API INTEGRATION TEST SUITE")
print("#" * 80)

#
# SETUP
#

print_test(
    "SETUP - CREATE SOURCE"
)

response = requests.get(
    f"{BASE_URL}/sources"
)

assert_status(
    response,
    200
)

sources = response.json()

assert len(sources) > 0

created_source_id = sources[0]["source_id"]

print("PASS")

#
# TEST 1
#

print_test(
    "TEST 1 - CREATE INGESTION"
)

response = requests.post(
    f"{BASE_URL}/ingestions",
    json={
        "source_id": created_source_id
    }
)

assert_status(
    response,
    201
)

body = response.json()

assert (
    body["source_id"]
    == created_source_id
)

assert (
    body["status"]
    == "RECEIVED"
)

print("PASS")

#
# TEST 2
#

print_test(
    "TEST 2 - INVALID SOURCE"
)

response = requests.post(
    f"{BASE_URL}/ingestions",
    json={
        "source_id":
            "00000000-0000-0000-0000-000000000000"
    }
)

assert_status(
    response,
    404
)

print("PASS")

print()
print("#" * 80)
print("ALL INGESTION API TESTS PASSED")
print("#" * 80)
print()