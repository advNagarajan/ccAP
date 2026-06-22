import logging
from datetime import datetime, UTC
from uuid import UUID
from sqlalchemy import text, select
from sqlalchemy.orm import Session

from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.metadata_profile import MetadataProfile
from app.schemas.fallback import DatabaseConnectionDetails
from app.pubsub.publisher import publish_fallback_landing_created, publish_job_completed, publish_job_failed
from app.services.job_stage_service import update_job_status_from_artifacts

logger = logging.getLogger("backup_table_service")


def escape_identifier(name: str, dialect: str) -> str:
    dialect = dialect.lower()
    if dialect == "mysql":
        return "`" + name.replace("`", "``") + "`"
    else:
        return '"' + name.replace('"', '""') + '"'


def map_observed_type_to_sql(observed_types: list, dialect: str = "postgresql") -> str:
    dialect = dialect.lower()
    if not observed_types:
        return "TEXT" if dialect != "mysql" else "VARCHAR(255)"
    
    t = str(observed_types[0]).lower()
    
    if t in ("int", "integer", "bigint", "smallint"):
        if dialect == "sqlite":
            return "INTEGER"
        return "BIGINT"
    
    if t in ("float", "double", "real", "numeric", "decimal"):
        if dialect == "sqlite":
            return "REAL"
        if dialect == "mysql":
            return "DECIMAL(18, 4)"
        return "NUMERIC"
    
    if t in ("bool", "boolean"):
        if dialect == "sqlite":
            return "INTEGER"
        if dialect == "mysql":
            return "TINYINT(1)"
        return "BOOLEAN"
    
    if t in ("date",):
        if dialect == "sqlite":
            return "TEXT"
        return "DATE"
    
    if t in ("datetime", "timestamp"):
        if dialect == "sqlite":
            return "TEXT"
        if dialect == "mysql":
            return "DATETIME"
        return "TIMESTAMP WITHOUT TIME ZONE"
    
    if t in ("dict", "list", "json", "jsonb"):
        if dialect == "sqlite":
            return "TEXT"
        if dialect == "mysql":
            return "JSON"
        return "JSONB"
    
    if dialect == "mysql":
        return "VARCHAR(255)"
    return "TEXT"


def generate_ddl_for_request(
    request: SchemaFallbackRequest,
    db: Session,
    dialect: str = "postgresql",
    schema_name: str | None = "raw_landing",
    table_name: str | None = None
) -> str:
    """
    Constructs the CREATE TABLE DDL string based on MetadataProfile columns and the database dialect.
    """
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

    # Determine table name if not provided
    if not table_name:
        timestamp_str = request.created_at.strftime("%Y%m%d_%H%M%S") if request.created_at else datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        table_name = f"backup_{request.job_id.hex}_{timestamp_str}"

    dialect = dialect.lower()
    escaped_table = escape_identifier(table_name, dialect)
    
    if schema_name:
        escaped_schema = escape_identifier(schema_name, dialect)
        full_table_name = f"{escaped_schema}.{escaped_table}"
    else:
        full_table_name = escaped_table

    cols_ddl = []
    for col in columns:
        col_name = col.get("name")
        if not col_name:
            continue
        col_type = map_observed_type_to_sql(col.get("observed_types", []), dialect)
        escaped_col_name = escape_identifier(col_name, dialect)
        cols_ddl.append(f"{escaped_col_name} {col_type}")

    if not cols_ddl:
        raise ValueError("No valid columns found for table DDL generation.")

    columns_sql = ", ".join(cols_ddl)
    
    ddl_parts = []
    if schema_name and dialect != "sqlite":
        ddl_parts.append(f"CREATE SCHEMA IF NOT EXISTS {escaped_schema};")
            
    ddl_parts.append(f"CREATE TABLE {full_table_name} ({columns_sql});")
    
    return "\n".join(ddl_parts)


def create_backup_table_for_request(
    request_id: UUID,
    approved_by: str | None,
    review_notes: str | None,
    db: Session,
    connection_details: DatabaseConnectionDetails | None = None
) -> str:
    """
    Approves a pending SchemaFallbackRequest, generates backup table DDL (dialect-aware),
    executes it (locally or on custom remote db), updates job state to COMPLETED,
    and publishes fallback-landing-created and job-completed events.
    """
    request = db.get(SchemaFallbackRequest, request_id)
    if not request:
        raise ValueError(f"SchemaFallbackRequest not found: {request_id}")

    if request.request_status != "PENDING":
        raise ValueError(f"Request is not PENDING (current status: {request.request_status})")

    dialect = "postgresql"
    schema_name = "raw_landing"
    table_name = None
    
    if connection_details:
        dialect = connection_details.db_type or "postgresql"
        schema_name = connection_details.schema_name
        table_name = connection_details.table_name

    # Determine default table name if not set
    if not table_name:
        timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        table_name = f"backup_{request.job_id.hex}_{timestamp_str}"
        
    full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name

    # Generate DDL
    ddl = generate_ddl_for_request(
        request=request,
        db=db,
        dialect=dialect,
        schema_name=schema_name,
        table_name=table_name
    )

    logger.info(f"Executing DDL for backup table on dialect={dialect}: {full_table_name}")

    if connection_details and (connection_details.host or connection_details.db_type == "sqlite"):
        # Custom connection
        from sqlalchemy import create_engine
        if dialect == "sqlite":
            db_path = connection_details.database or ":memory:"
            conn_url = f"sqlite:///{db_path}"
        else:
            conn_url = f"{dialect}://{connection_details.username}:{connection_details.password}@{connection_details.host}:{connection_details.port}/{connection_details.database}"
        
        ext_engine = create_engine(conn_url)
        with ext_engine.connect() as conn:
            for stmt in ddl.strip().split(";"):
                if stmt.strip():
                    conn.execute(text(stmt.strip() + ";"))
            conn.commit()
    else:
        # Default connection
        for stmt in ddl.strip().split(";"):
            if stmt.strip():
                db.execute(text(stmt.strip() + ";"))

    # Update request
    request.request_status = "APPROVED"
    request.backup_table_name = full_table_name
    request.approved_by = approved_by
    request.approved_at = datetime.now(UTC)
    request.review_notes = review_notes

    # Update Job
    job = db.get(Job, request.job_id)
    if job:
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

    db.commit()

    # Re-evaluate overall job status from artifact states
    update_job_status_from_artifacts(request.job_id, db)

    # Publish Completed & Fallback landing created events, passing artifact_id
    source_id = job.source_id if job else None
    publish_fallback_landing_created(request.job_id, source_id, full_table_name)
    publish_job_completed(
        request.job_id,
        source_id,
        recommendations_count=0,
        target_name=full_table_name,
        artifact_id=str(request.artifact_id)
    )

    logger.info(f"Backup table {full_table_name} created and request approved successfully.")
    return full_table_name


def reject_fallback_request(
    request_id: UUID,
    rejected_by: str | None,
    review_notes: str | None,
    db: Session
):
    """
    Rejects a pending SchemaFallbackRequest, failing the parent Job, and publishes job-failed event.
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

    # Re-evaluate overall job status from artifact states
    update_job_status_from_artifacts(request.job_id, db)

    # Publish Failed event, passing artifact_id
    source_id = job.source_id if job else None
    publish_job_failed(
        job_id=request.job_id,
        source_id=source_id,
        error_message=f"Fallback request rejected by user: {review_notes}",
        artifact_id=str(request.artifact_id)
    )

    logger.info(f"Fallback request {request_id} rejected successfully.")
