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

        details = {
            "connector_name": "UNKNOWN",
            "artifact_count": 0,
            "steps": {
                "loading_source": "PENDING",
                "artifact_discovery": "PENDING"
            },
            "artifacts": []
        }

        acq_stage = start_stage(
            job.job_id,
            "Dataset Acquisition",
            db,
            details=details
        )

        source = db.get(Source, job.source_id)

        if source is None:
            details["steps"]["loading_source"] = "FAILED"
            acq_stage.details = details
            db.commit()
            raise Exception("Source not found")

        details["connector_name"] = source.source_type
        details["steps"]["loading_source"] = "COMPLETED"
        acq_stage.details = details
        db.commit()

        connector = CONNECTORS.get(source.source_type)

        if connector is None:
            details["steps"]["artifact_discovery"] = "FAILED"
            acq_stage.details = details
            db.commit()
            raise Exception(f"No connector registered for {source.source_type}")

        job.current_stage = "Discovering Artifacts"

        db.commit()

        try:
            artifacts = connector.list_artifacts(source)

            unprocessed_artifacts = connector.get_unprocessed_artifacts(
                source,
                artifacts,
                db
            )
            details["steps"]["artifact_discovery"] = "COMPLETED"
            details["artifact_count"] = len(unprocessed_artifacts)
            acq_stage.details = details
            db.commit()
        except Exception as disc_err:
            details["steps"]["artifact_discovery"] = "FAILED"
            acq_stage.details = details
            db.commit()
            raise disc_err

        if not unprocessed_artifacts:

            print(
                f"No unprocessed artifacts found for "
                f"source {source.source_id}"
            )

            job.current_stage = "No New Artifacts"

            db.commit()

            complete_stage(
                acq_stage.stage_history_id,
                db,
                details
            )

            return

        total_records = 0

        for artifact in unprocessed_artifacts:
            artifact_info = {
                "name": artifact.artifact_name,
                "external_id": artifact.external_id,
                "status": "PENDING"
            }
            details["artifacts"].append(artifact_info)
            acq_stage.details = details
            db.commit()

            try:

                job.current_stage = f"Processing {artifact.artifact_name}"

                db.commit()

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

                artifact_info["status"] = "COMPLETED"
                artifact_info["record_count"] = record_count
                acq_stage.details = details
                db.commit()

                print(
                    f"Processed {artifact.artifact_name} "
                    f"({record_count} records)"
                )

            except Exception as artifact_error:
                artifact_info["status"] = "FAILED"
                artifact_info["error"] = str(artifact_error)
                acq_stage.details = details
                db.commit()

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

        complete_stage(
            acq_stage.stage_history_id,
            db,
            details
        )

        print(
            f"Published dataset.received for "
            f"{len(unprocessed_artifacts)} artifacts"
        )

    except Exception as e:

        print(f"Failed job {job_id}: {e}")

        if 'acq_stage' in locals() and acq_stage is not None:
            try:
                fail_stage(
                    acq_stage.stage_history_id,
                    e,
                    db
                )
            except Exception:
                pass

        raise

    finally:

        db.close()