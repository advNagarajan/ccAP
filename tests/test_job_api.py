import requests

BASE_URL = "http://127.0.0.1:8000"

created_job_id = None


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
print("JOB API INTEGRATION TEST SUITE")
print("#" * 80)

#
# SETUP
#

print_test("SETUP - CREATE JOB")

response = requests.get(f"{BASE_URL}/sources")

assert_status(response, 200)

sources = response.json()

assert len(sources) > 0

source_id = sources[0]["source_id"]

response = requests.post(
    f"{BASE_URL}/ingestions",
    json={
        "source_id": source_id
    }
)

assert_status(response, 201)

created_job_id = response.json()["job_id"]

print("PASS")

#
# TEST 1
#

print_test("TEST 1 - GET ALL JOBS")

response = requests.get(f"{BASE_URL}/jobs")

assert_status(response, 200)

jobs = response.json()

assert len(jobs) > 0

print("PASS")

#
# TEST 2
#

print_test("TEST 2 - GET JOB BY ID")

response = requests.get(
    f"{BASE_URL}/jobs/{created_job_id}"
)

assert_status(response, 200)

job = response.json()

assert (
    job["job_id"]
    == created_job_id
)

assert (
    job["status"]
    == "RECEIVED"
)

print("PASS")

#
# TEST 3
#

print_test("TEST 3 - FILTER JOBS BY STATUS")

response = requests.get(
    f"{BASE_URL}/jobs?status=RECEIVED"
)

assert_status(response, 200)

jobs = response.json()

assert len(jobs) > 0

for job in jobs:

    assert (
        job["status"]
        == "RECEIVED"
    )

print("PASS")

#
# TEST 4
#

print_test("TEST 4 - GET NONEXISTENT JOB")

response = requests.get(
    f"{BASE_URL}/jobs/00000000-0000-0000-0000-000000000000"
)

assert_status(response, 404)

print("PASS")

print()
print("#" * 80)
print("ALL JOB API TESTS PASSED")
print("#" * 80)
print()