import json
from datetime import datetime, UTC
from uuid import UUID

from app.db.database import SessionLocal

from app.models.job import Job
from app.models.source import Source

from app.constants.job_status import JobStatus

from app.connectors.registry import CONNECTORS
from app.parsers.registry import PARSERS

from app.services.artifact_service import mark_failed

from app.services.job_stage_service import (
    start_stage,
    complete_stage,
    fail_stage
)

from app.pubsub.publisher import (
    publish_dataset_received,
    publish_job_failed
)


def process_ingestion_requested(message_data: bytes):

    payload = json.loads(message_data.decode("utf-8"))
    job_id = UUID(payload["job_id"])

    db = SessionLocal()

    try:

        job = db.get(Job, job_id)

        if job is None:
            print(f"Job {job_id} not found")
            return

        print(f"Processing job {job_id}")

        job.status = JobStatus.RUNNING
        job.current_stage = "Loading Source"
        job.started_at = datetime.now(UTC)

        db.commit()

        loading_stage = start_stage(
            job.job_id,
            "Loading Source",
            db
        )

        source = db.get(Source, job.source_id)

        if source is None:
            raise Exception("Source not found")

        complete_stage(
            loading_stage.stage_history_id,
            db
        )

        connector = CONNECTORS.get(source.source_type)

        if connector is None:
            raise Exception(f"No connector registered for {source.source_type}")

        job.current_stage = "Discovering Artifacts"

        db.commit()

        artifact_stage = start_stage(
            job.job_id,
            "Artifact Discovery",
            db
        )

        artifacts = connector.list_artifacts(source)

        unprocessed_artifacts = connector.get_unprocessed_artifacts(
            source,
            artifacts,
            db
        )

        complete_stage(
            artifact_stage.stage_history_id,
            db,
            {"artifact_count": len(unprocessed_artifacts)}
        )

        if not unprocessed_artifacts:

            print(
                f"No unprocessed artifacts found for "
                f"source {source.source_id}"
            )

            job.current_stage = "No New Artifacts"

            db.commit()

            return

        total_records = 0

        for artifact in unprocessed_artifacts:

            processing_stage = None

            try:

                job.current_stage = f"Processing {artifact.artifact_name}"

                db.commit()

                processing_stage = start_stage(
                    job.job_id,
                    f"Processing {artifact.artifact_name}",
                    db
                )

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

                record_count = len(dataset.records)
                total_records += record_count

                publish_dataset_received(
                    job.job_id,
                    source.source_id,
                    artifact.external_id
                )

                complete_stage(
                    processing_stage.stage_history_id,
                    db,
                    {
                        "record_count": record_count,
                        "artifact_external_id": artifact.external_id
                    }
                )

                print(
                    f"Processed {artifact.artifact_name} "
                    f"({record_count} records)"
                )

            except Exception as artifact_error:

                if processing_stage is not None:
                    fail_stage(
                        processing_stage.stage_history_id,
                        artifact_error,
                        db
                    )

                mark_failed(
                    source.source_id,
                    artifact,
                    str(artifact_error),
                    db
                )

                print(
                    f"Failed artifact "
                    f"{artifact.artifact_name}: "
                    f"{artifact_error}"
                )

        print(
            f"Processed {len(unprocessed_artifacts)} artifacts "
            f"containing {total_records} records"
        )

        job.current_stage = "Dataset Published"

        db.commit()

        print(
            f"Published dataset.received for "
            f"{len(unprocessed_artifacts)} artifacts"
        )

    except Exception as e:

        print(f"Failed job {job_id}: {e}")

        try:

            failure_stage = start_stage(
                job_id,
                "Pipeline Failure",
                db
            )

            fail_stage(
                failure_stage.stage_history_id,
                e,
                db
            )

            job = db.get(Job, job_id)

            if job is not None:

                job.status = JobStatus.FAILED
                job.current_stage = "Failed"
                job.error_message = str(e)

                db.commit()

                publish_job_failed(
                    job.job_id,
                    job.source_id,
                    str(e)
                )

        except Exception:
            pass

    finally:

        db.close()