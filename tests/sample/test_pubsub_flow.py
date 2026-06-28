import time
import requests

BASE_URL = "http://127.0.0.1:8000"


print("Creating ingestion...")

sources = requests.get(
    f"{BASE_URL}/sources"
).json()

source_id = sources[0]["source_id"]

response = requests.post(
    f"{BASE_URL}/ingestions",
    json={
        "source_id": source_id
    }
)

assert response.status_code == 201

job_id = response.json()["job_id"]

print(f"Created job {job_id}")

time.sleep(7)

response = requests.get(
    f"{BASE_URL}/jobs/{job_id}"
)

assert response.status_code == 200

job = response.json()

assert job["status"] == "COMPLETED"

print("PASS")