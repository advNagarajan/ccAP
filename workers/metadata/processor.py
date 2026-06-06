import json


def process_dataset_received(
    message_data: bytes
):

    payload = json.loads(
        message_data.decode("utf-8")
    )

    print()

    print("=== DATASET RECEIVED ===")

    print(payload)

    print()