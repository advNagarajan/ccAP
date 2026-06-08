import json

from sqlalchemy import select

from app.db.database import SessionLocal

from app.models.source import Source
from app.models.artifact_record import ArtifactRecord

from app.connectors.registry import CONNECTORS
from app.parsers.registry import PARSERS

from app.services.metadata_service import (
    extract_metadata,
    metadata_to_dict,
    save_metadata
)


def process_dataset_received(
    message_data: bytes
):

    payload = json.loads(
        message_data.decode("utf-8")
    )

    source_id = payload["source_id"]

    artifact_external_id = payload[
        "artifact_external_id"
    ]

    db = SessionLocal()

    try:

        print()

        print(
            "=== DATASET RECEIVED ==="
        )

        print(payload)

        source = db.get(
            Source,
            source_id
        )

        if source is None:
            raise Exception(
                "Source not found"
            )

        artifact_record = db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.source_id ==
                source_id,
                ArtifactRecord.external_artifact_id ==
                artifact_external_id
            )
        ).scalar_one_or_none()

        if artifact_record is None:
            raise Exception(
                "Artifact record not found"
            )

        connector = CONNECTORS.get(
            source.source_type
        )

        if connector is None:
            raise Exception(
                f"No connector registered for "
                f"{source.source_type}"
            )

        artifact = next(
            (
                candidate
                for candidate in connector.list_artifacts(
                    source
                )
                if candidate.external_id ==
                artifact_external_id
            ),
            None
        )

        if artifact is None:
            raise Exception(
                "Artifact not found in source"
            )

        raw_data = connector.extract_sample(
            source,
            artifact
        )

        parser = PARSERS.get(
            raw_data.format_type
        )

        if parser is None:
            raise Exception(
                f"No parser registered for "
                f"{raw_data.format_type}"
            )

        dataset = parser.parse(
            raw_data
        )

        metadata = extract_metadata(
            dataset,
            artifact.metadata
        )

        profile = save_metadata(
            artifact_record.artifact_id,
            metadata_to_dict(
                metadata
            ),
            db
        )

        print()

        print(
            "Metadata Profile Created"
        )

        print(
            f"Metadata Profile ID: "
            f"{profile.metadata_profile_id}"
        )

        print(
            f"Artifact ID: "
            f"{artifact_record.artifact_id}"
        )

        print()

    finally:

        db.close()