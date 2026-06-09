import json
from uuid import UUID

from sqlalchemy import select

from app.db.database import SessionLocal

from app.models.job import Job
from app.models.source import Source
from app.models.artifact_record import ArtifactRecord

from app.constants.job_status import JobStatus

from app.connectors.registry import CONNECTORS
from app.parsers.registry import PARSERS

from app.services.artifact_service import mark_processed

from app.services.metadata_service import (
    extract_metadata,
    metadata_to_dict,
    save_metadata
)

from app.services.job_stage_service import (
    start_stage,
    complete_stage,
    fail_stage
)

from app.pubsub.publisher import (
    publish_metadata_extracted,
    publish_job_failed
)


def process_dataset_received(message_data: bytes):

    payload = json.loads(message_data.decode("utf-8"))

    source_id = payload["source_id"]
    job_id = UUID(payload["job_id"])
    artifact_external_id = payload["artifact_external_id"]

    db = SessionLocal()

    metadata_stage = None
    publish_stage = None

    try:

        print()
        print("=== DATASET RECEIVED ===")
        print(payload)

        job = db.get(Job, job_id)

        if job is None:
            raise Exception("Job not found")

        source = db.get(Source, source_id)

        if source is None:
            raise Exception("Source not found")

        job.current_stage = "Metadata Extraction"

        db.commit()

        metadata_stage = start_stage(
            job.job_id,
            "Metadata Extraction",
            db
        )

        artifact_record = db.execute(
            select(ArtifactRecord).where(
                ArtifactRecord.source_id == source_id,
                ArtifactRecord.external_artifact_id == artifact_external_id
            )
        ).scalar_one_or_none()

        if artifact_record is None:
            raise Exception("Artifact record not found")

        connector = CONNECTORS.get(source.source_type)

        if connector is None:
            raise Exception(
                f"No connector registered for {source.source_type}"
            )

        artifact = connector.get_artifact(
            source,
            artifact_external_id
        )

        if artifact is None:
            raise Exception("Artifact not found in source")

        raw_data = connector.extract_sample(
            source,
            artifact
        )

        parser = PARSERS.get(raw_data.format_type)

        if parser is None:
            raise Exception(
                f"No parser registered for {raw_data.format_type}"
            )

        dataset = parser.parse(raw_data)

        metadata = extract_metadata(
            dataset,
            artifact.metadata
        )

        profile = save_metadata(
            job_id,
            artifact_record.artifact_id,
            metadata_to_dict(metadata),
            db
        )

        mark_processed(
            source.source_id,
            artifact,
            db
        )

        complete_stage(
            metadata_stage.stage_history_id,
            db,
            {
                "metadata_profile_id": str(profile.metadata_profile_id),
                "artifact_id": str(artifact_record.artifact_id)
            }
        )

        job.current_stage = "Metadata Published"

        db.commit()

        publish_stage = start_stage(
            job.job_id,
            "Metadata Published",
            db
        )

        publish_metadata_extracted(
            job.job_id,
            artifact_record.artifact_id,
            profile.metadata_profile_id
        )

        complete_stage(
            publish_stage.stage_history_id,
            db,
            {
                "metadata_profile_id": str(profile.metadata_profile_id)
            }
        )

        db.commit()

        print()
        print("Metadata Profile Created")
        print(f"Metadata Profile ID: {profile.metadata_profile_id}")
        print(f"Artifact ID: {artifact_record.artifact_id}")
        print()

    except Exception as e:

        print(f"Metadata extraction failed: {e}")

        if metadata_stage is not None:

            try:

                fail_stage(
                    metadata_stage.stage_history_id,
                    e,
                    db
                )

            except Exception:
                pass

        if publish_stage is not None:

            try:

                fail_stage(
                    publish_stage.stage_history_id,
                    e,
                    db
                )

            except Exception:
                pass

        try:

            job = db.get(Job, job_id)

            if job is not None:

                job.status = JobStatus.FAILED
                job.current_stage = "Metadata Extraction Failed"
                job.error_message = str(e)

                db.commit()

                publish_job_failed(
                    job.job_id,
                    job.source_id,
                    str(e)
                )

        except Exception:
            pass

        raise

    finally:

        db.close()