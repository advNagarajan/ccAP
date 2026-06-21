from pprint import pprint
from unittest.mock import patch
from google.cloud import storage
from app.connectors.gcs_connector import GCSConnector

from app.db.database import SessionLocal

from app.models.db.source import Source
from app.models.db.artifact_record import ArtifactRecord

from app.connectors.registry import CONNECTORS
from app.parsers.registry import PARSERS

from app.services.artifact_service import (
    discover_new_artifacts,
    mark_processed
)


SOURCE_ID = "ad7e9ad3-af31-4a36-af2b-4b26172d8b5f"


@patch.object(GCSConnector, "_get_client")
def test_gcs_ingestion_pipeline(mock_get_client):
    mock_get_client.return_value = storage.Client()

    db = SessionLocal()

    try:

        print("\n=== SOURCE LOOKUP ===")

        source = db.get(Source, SOURCE_ID)

        assert source is not None

        print(f"Source ID: {source.source_id}")
        print(f"Source Name: {source.name}")
        print(f"Source Type: {source.source_type}")

        pprint(source.connection_details)

        print("\n=== CONNECTOR LOOKUP ===")

        connector = CONNECTORS.get(source.source_type)

        assert connector is not None

        print(
            f"Connector Found: "
            f"{connector.__class__.__name__}"
        )

        print("\n=== ARTIFACT DISCOVERY ===")

        artifacts = connector.list_artifacts(source)

        assert len(artifacts) > 0

        print(
            f"Artifacts Discovered: "
            f"{len(artifacts)}"
        )

        for artifact in artifacts:

            print(
                f"- {artifact.artifact_name}"
            )

            pprint(artifact.metadata)

        print("\n=== ARTIFACT REGISTRATION ===")

        new_artifacts = discover_new_artifacts(
            source.source_id,
            artifacts,
            db
        )

        print(
            f"New Artifacts Found: "
            f"{len(new_artifacts)}"
        )

        if not new_artifacts:

            print(
                "No new artifacts discovered. "
                "Using all discovered artifacts "
                "for validation."
            )

            new_artifacts = artifacts

        total_records = 0

        print("\n=== EXTRACTION AND PARSING ===")

        for artifact in new_artifacts:

            print(
                f"\nProcessing: "
                f"{artifact.artifact_name}"
            )

            raw_data = connector.extract_sample(
                source,
                artifact
            )

            assert raw_data is not None
            assert raw_data.content is not None

            print(
                f"Format Type: "
                f"{raw_data.format_type}"
            )

            print(
                f"Source Type: "
                f"{raw_data.source_type}"
            )

            print(
                f"Source Name: "
                f"{raw_data.source_name}"
            )

            print("\nRaw Content:")

            print(raw_data.content)

            parser = PARSERS.get(
                raw_data.format_type
            )

            assert parser is not None

            print(
                f"\nParser: "
                f"{parser.__class__.__name__}"
            )

            dataset = parser.parse(
                raw_data
            )

            assert dataset is not None

            record_count = len(
                dataset.records
            )

            total_records += record_count

            print(
                f"\nDataset Records: "
                f"{record_count}"
            )

            print("\nParsed Records:")

            pprint(dataset.records)

            mark_processed(
                source.source_id,
                artifact,
                db
            )

            print(
                "\nArtifact marked "
                "as PROCESSED"
            )

        print("\n=== DATABASE VERIFICATION ===")

        records = (
            db.query(ArtifactRecord)
            .filter(
                ArtifactRecord.source_id
                == source.source_id
            )
            .all()
        )

        assert len(records) > 0

        for record in records:

            print(
                f"{record.artifact_name} "
                f"=> {record.status}"
            )

        print("\n=== SUMMARY ===")

        print(
            f"Artifacts Processed: "
            f"{len(new_artifacts)}"
        )

        print(
            f"Records Parsed: "
            f"{total_records}"
        )

        assert total_records > 0

        print(
            "\nSUCCESS: End-to-end "
            "ingestion pipeline passed."
        )

    finally:

        db.close()