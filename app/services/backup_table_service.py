import logging
from datetime import datetime, UTC
from uuid import UUID
from sqlalchemy import text, select
from sqlalchemy.orm import Session

from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.metadata_profile import MetadataProfile
from app.pubsub.publisher import publish_fallback_landing_created

logger = logging.getLogger("backup_table_service")


def map_observed_type_to_sql(observed_types: list) -> str:
    if not observed_types:
        return "TEXT"
    t = str(observed_types[0]).lower()
    if t in ("int", "integer", "bigint", "smallint"):
        return "BIGINT"
    if t in ("float", "double", "real", "numeric", "decimal"):
        return "NUMERIC"
    if t in ("bool", "boolean"):
        return "BOOLEAN"
    if t in ("date",):
        return "DATE"
    if t in ("datetime", "timestamp"):
        return "TIMESTAMP WITHOUT TIME ZONE"
    if t in ("dict", "list", "json", "jsonb"):
        return "JSONB"
    return "TEXT"


def create_backup_table_for_request(
    request_id: UUID,
    approved_by: str | None,
    review_notes: str | None,
    db: Session
) -> str:
    """
    Approves a pending SchemaFallbackRequest, generates backup table, updates job state,
    and publishes a fallback-landing-created event.
    """
    request = db.get(SchemaFallbackRequest, request_id)
    if not request:
        raise ValueError(f"SchemaFallbackRequest not found: {request_id}")

    if request.request_status != "PENDING":
        raise ValueError(f"Request is not PENDING (current status: {request.request_status})")

    # Fetch associated MetadataProfile
    profile = db.execute(
        select(MetadataProfile).where(
            MetadataProfile.job_id == request.job_id,
            MetadataProfile.artifact_id == request.artifact_id
        )
    ).scalar_one_or_none()

    if not profile:
        raise ValueError(f"MetadataProfile not found for job={request.job_id} and artifact={request.artifact_id}")

    columns = profile.metadata_json.get("columns", [])
    if not columns:
        raise ValueError("MetadataProfile contains no columns; cannot generate table DDL.")

    # Format backup table name: backup_<job_id_hex>_<timestamp>
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    raw_table_name = f"backup_{request.job_id.hex}_{timestamp_str}"
    full_table_name = f"raw_landing.{raw_table_name}"

    # Build SQL DDL
    cols_ddl = []
    for col in columns:
        col_name = col.get("name")
        if not col_name:
            continue
        col_type = map_observed_type_to_sql(col.get("observed_types", []))
        # Protect column names from SQL injection/reserved words by wrapping in double quotes
        escaped_col_name = '"' + col_name.replace('"', '""') + '"'
        cols_ddl.append(f"{escaped_col_name} {col_type}")

    if not cols_ddl:
        raise ValueError("No valid columns found for table DDL generation.")

    columns_sql = ", ".join(cols_ddl)
    create_schema_sql = "CREATE SCHEMA IF NOT EXISTS raw_landing;"
    create_table_sql = f"CREATE TABLE {full_table_name} ({columns_sql});"

    logger.info(f"Executing DDL for backup table: {full_table_name}")
    db.execute(text(create_schema_sql))
    db.execute(text(create_table_sql))

    # Update request
    request.request_status = "APPROVED"
    request.backup_table_name = full_table_name
    request.approved_by = approved_by
    request.approved_at = datetime.now(UTC)
    request.review_notes = review_notes

    # Update Job
    job = db.get(Job, request.job_id)
    if job:
        job.status = "FALLBACK_LANDING_CREATED"
        job.error_message = None

    # Log Stage
    stage = JobStageHistory(
        job_id=request.job_id,
        stage_name="Fallback Landing Created",
        status="COMPLETED",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        details={
            "backup_table_name": full_table_name,
            "approved_by": approved_by,
            "review_notes": review_notes
        }
    )
    db.add(stage)

    # Publish Completed event
    source_id = job.source_id if job else None
    publish_fallback_landing_created(request.job_id, source_id, full_table_name)

    db.commit()
    logger.info(f"Backup table {full_table_name} created and request approved successfully.")
    return full_table_name


def reject_fallback_request(
    request_id: UUID,
    rejected_by: str | None,
    review_notes: str | None,
    db: Session
):
    """
    Rejects a pending SchemaFallbackRequest, failing the parent Job.
    """
    request = db.get(SchemaFallbackRequest, request_id)
    if not request:
        raise ValueError(f"SchemaFallbackRequest not found: {request_id}")

    if request.request_status != "PENDING":
        raise ValueError(f"Request is not PENDING (current status: {request.request_status})")

    request.request_status = "REJECTED"
    request.rejected_by = rejected_by
    request.rejected_at = datetime.now(UTC)
    request.review_notes = review_notes

    # Update Job
    job = db.get(Job, request.job_id)
    if job:
        job.status = "FAILED"
        job.error_message = f"Fallback request rejected by user: {review_notes}"

    # Log Stage
    stage = JobStageHistory(
        job_id=request.job_id,
        stage_name="Fallback Request Rejected",
        status="FAILED",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        details={
            "rejected_by": rejected_by,
            "review_notes": review_notes
        }
    )
    db.add(stage)

    db.commit()
    logger.info(f"Fallback request {request_id} rejected successfully.")
