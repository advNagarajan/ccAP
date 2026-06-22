import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.job_stage_history import JobStageHistory
from app.services.drift_service import compute_schema_drift
from app.services.backup_table_service import create_backup_table_for_request, reject_fallback_request
from workers.drift.processor import process_schema_drift
from workers.validation.processor import process_schema_validation


# ==========================================
# 1. DRIFT CALCULATION UNIT TESTS
# ==========================================

def test_compute_schema_drift_no_drift():
    metadata_json = {
        "columns": [
            {"name": "id", "observed_types": ["int"]},
            {"name": "name", "observed_types": ["str"]}
        ]
    }
    schema_definition = {
        "fields": [
            {"name": "id", "type": "INTEGER"},
            {"name": "name", "type": "VARCHAR"}
        ]
    }
    column_mapping = {"id": "id", "name": "name"}

    results = compute_schema_drift(metadata_json, schema_definition, column_mapping)
    assert results["drift_status"] == "NO_DRIFT"
    assert results["drift_score"] == 0.0
    assert len(results["drift_summary"]["new_columns"]) == 0
    assert len(results["drift_summary"]["removed_columns"]) == 0
    assert len(results["drift_summary"]["datatype_changes"]) == 0
    assert len(results["drift_summary"]["renamed_columns"]) == 0


def test_compute_schema_drift_warning_drift():
    schema_definition_warn = {
        "fields": [{"name": f"col{i}", "type": "VARCHAR"} for i in range(10)]
    }
    metadata_json_warn = {
        "columns": [{"name": f"col{i}", "observed_types": ["str"]} for i in range(10)]
    }
    column_mapping_warn = {f"col{i}": f"col{i}" for i in range(10)}

    # Modify one column name (rename)
    column_mapping_warn["col0"] = "col9"  # rename
    # Total target = 10. 1 rename = 10% score.
    results = compute_schema_drift(metadata_json_warn, schema_definition_warn, column_mapping_warn)
    assert results["drift_status"] == "WARNING_DRIFT"
    assert results["drift_score"] == 10.0


def test_compute_schema_drift_datatype_normalization():
    # Target VARCHAR, Source text/STRING (should normalize to "str" and not drift)
    metadata_json = {
        "columns": [
            {"name": "bio", "observed_types": ["text"]},
            {"name": "notes", "observed_types": ["STRING"]}
        ]
    }
    schema_definition = {
        "fields": [
            {"name": "bio", "type": "VARCHAR"},
            {"name": "notes", "type": "VARCHAR(255)"}
        ]
    }
    column_mapping = {"bio": "bio", "notes": "notes"}

    results = compute_schema_drift(metadata_json, schema_definition, column_mapping)
    assert results["drift_status"] == "NO_DRIFT"
    assert results["drift_score"] == 0.0


# ==========================================
# 2. WORKER INTEGRATION & FALLBACK TRIGGER TESTS
# ==========================================

@patch("workers.validation.processor.start_stage")
@patch("workers.validation.processor.complete_stage")
@patch("workers.validation.processor.publish_schema_validated")
@patch("workers.validation.processor.publish_fallback_requested")
def test_validation_skipped_creates_fallback_request(mock_pub_fallback, mock_publish, mock_complete, mock_start):
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={"columns": []}
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.UUID(profile_id),
        target_id=None,  # Skipped Target mapping
        confidence_score=0.0,
        column_mapping={},
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="No match"
    )

    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")

    def db_get(model, ident):
        if model == MetadataProfile:
            return profile
        if model == LandingInference:
            return inference
        if model == Job:
            return job
        return None
    db.get = db_get

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()
    mock_start.return_value = mock_stage

    added_objects = []
    db.add = lambda x: added_objects.append(x)

    val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

    assert val_record.validation_status == "SKIPPED"
    fallback_requests = [x for x in added_objects if isinstance(x, SchemaFallbackRequest)]
    assert len(fallback_requests) == 1
    assert fallback_requests[0].request_reason == "TARGET_NOT_FOUND"
    assert fallback_requests[0].request_status == "PENDING"
    assert job.status == "PENDING_REVIEW"


@patch("workers.drift.processor.start_stage")
@patch("workers.drift.processor.complete_stage")
@patch("workers.drift.processor.publish_drift_detected")
@patch("workers.drift.processor.publish_fallback_requested")
def test_critical_drift_creates_fallback_request(mock_pub_fallback, mock_publish, mock_complete, mock_start):
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    validation_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    val_record = SchemaValidation(
        validation_id=uuid.UUID(validation_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        inference_id=uuid.UUID(inference_id),
        target_id=uuid.UUID(target_id),
        validation_status="WARNING",
        coverage_percentage=50.0,
        target_match_percentage=50.0,
        mapped_column_count=1,
        source_column_count=2,
        target_column_count=2,
        report_json={}
    )

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(str(uuid.uuid4())),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "new_col1", "observed_types": ["int"]},
                {"name": "new_col2", "observed_types": ["str"]}
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=profile.metadata_profile_id,
        target_id=uuid.UUID(target_id),
        confidence_score=0.9,
        column_mapping={"new_col1": "id"}
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"}
            ]
        }
    )

    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")

    def db_get(model, ident):
        if model == SchemaValidation:
            return val_record
        if model == LandingInference:
            return inference
        if model == MetadataProfile:
            return profile
        if model == TargetCatalog:
            return target
        if model == Job:
            return job
        return None
    db.get = db_get

    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    db.query.return_value = mock_query

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()
    mock_start.return_value = mock_stage

    added_objects = []
    db.add = lambda x: added_objects.append(x)

    drift_record = process_schema_drift(job_id, artifact_id, validation_id, db)

    assert drift_record.drift_status == "CRITICAL_DRIFT"
    fallback_requests = [x for x in added_objects if isinstance(x, SchemaFallbackRequest)]
    assert len(fallback_requests) == 1
    assert fallback_requests[0].request_reason == "CRITICAL_DRIFT"
    assert fallback_requests[0].request_status == "PENDING"
    assert job.status == "PENDING_REVIEW"


# ==========================================
# 3. APPROVAL FLOW, REJECTION, & IDEMPOTENCY
# ==========================================

# ==========================================

@patch("app.services.backup_table_service.publish_job_completed")
def test_create_backup_table_success(mock_completed):
    db = MagicMock()
    request_id = uuid.uuid4()
    job_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    request = SchemaFallbackRequest(
        request_id=request_id,
        job_id=job_id,
        artifact_id=artifact_id,
        request_reason="VALIDATION_FAILED",
        request_status="PENDING"
    )

    profile = MetadataProfile(
        job_id=job_id,
        artifact_id=artifact_id,
        metadata_json={
            "columns": [
                {"name": "user id", "observed_types": ["int"]},
                {"name": "group", "observed_types": ["str"]}
            ]
        }
    )

    job = Job(job_id=job_id, status="PENDING_REVIEW", source_id=uuid.uuid4())

    def db_get(model, ident):
        if model == SchemaFallbackRequest:
            return request
        if model == Job:
            return job
        return None
    db.get = db_get

    # Mock profile fetch query
    mock_profile_query = MagicMock()
    mock_profile_query.scalar_one_or_none.return_value = profile
    
    # Track DB execution calls
    exec_calls = []
    def db_execute(sql_text):
        exec_calls.append(sql_text)
        if "metadata_profiles" in str(sql_text):
            return mock_profile_query
        return MagicMock()
    db.execute = db_execute

    added_objects = []
    db.add = lambda x: added_objects.append(x)

    table_name = create_backup_table_for_request(request_id, "admin", "Approved for landing", db)

    assert request.request_status == "APPROVED"
    assert request.approved_by == "admin"
    assert request.review_notes == "Approved for landing"
    assert request.backup_table_name.startswith("raw_landing.backup_")
    assert job.status == "COMPLETED"

    ddl_executions = [str(call) for call in exec_calls if "CREATE TABLE" in str(call)]
    assert len(ddl_executions) == 1
    assert '"user id"' in ddl_executions[0]
    assert '"group"' in ddl_executions[0]

    stage_logs = [x for x in added_objects if isinstance(x, JobStageHistory)]
    assert len(stage_logs) == 1
    assert stage_logs[0].stage_name == "Fallback Landing Created"
    mock_completed.assert_called_once()


def test_create_backup_table_idempotent_error():
    db = MagicMock()
    request_id = uuid.uuid4()
    request = SchemaFallbackRequest(
        request_id=request_id,
        request_status="APPROVED"
    )
    db.get = lambda model, ident: request if model == SchemaFallbackRequest else None

    with pytest.raises(ValueError, match="Request is not PENDING"):
        create_backup_table_for_request(request_id, "admin", "Notes", db)


@patch("app.services.backup_table_service.publish_job_failed")
def test_reject_fallback_request_success(mock_failed):
    db = MagicMock()
    request_id = uuid.uuid4()
    job_id = uuid.uuid4()

    request = SchemaFallbackRequest(
        request_id=request_id,
        job_id=job_id,
        request_status="PENDING"
    )

    job = Job(job_id=job_id, status="PENDING_REVIEW")

    db.get = lambda model, ident: {SchemaFallbackRequest: request, Job: job}[model]

    added_objects = []
    db.add = lambda x: added_objects.append(x)

    reject_fallback_request(request_id, "admin", "Rejected notes", db)

    assert request.request_status == "REJECTED"
    assert request.rejected_by == "admin"
    assert request.rejected_at is not None
    assert request.review_notes == "Rejected notes"
    assert job.status == "FAILED"

    stage_logs = [x for x in added_objects if isinstance(x, JobStageHistory)]
    assert len(stage_logs) == 1
    assert stage_logs[0].stage_name == "Fallback Request Rejected"
    assert stage_logs[0].status == "FAILED"
    mock_failed.assert_called_once()


def test_map_observed_type_to_sql():
    from app.services.backup_table_service import map_observed_type_to_sql
    assert map_observed_type_to_sql(["int"], "postgresql") == "BIGINT"
    assert map_observed_type_to_sql(["int"], "sqlite") == "INTEGER"
    assert map_observed_type_to_sql(["dict"], "mysql") == "JSON"


@patch("app.services.backup_table_service.publish_job_completed")
@patch("sqlalchemy.create_engine")
def test_create_backup_table_custom_db(mock_engine, mock_completed):
    db = MagicMock()
    request_id = uuid.uuid4()
    job_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    request = SchemaFallbackRequest(
        request_id=request_id,
        job_id=job_id,
        artifact_id=artifact_id,
        request_reason="VALIDATION_FAILED",
        request_status="PENDING"
    )

    profile = MetadataProfile(
        job_id=job_id,
        artifact_id=artifact_id,
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["int"]}
            ]
        }
    )

    job = Job(job_id=job_id, status="PENDING_REVIEW", source_id=uuid.uuid4())

    def db_get(model, ident):
        if model == SchemaFallbackRequest:
            return request
        if model == Job:
            return job
        return None
    db.get = db_get

    mock_profile_query = MagicMock()
    mock_profile_query.scalar_one_or_none.return_value = profile
    
    def db_execute(sql_text):
        if "metadata_profiles" in str(sql_text):
            return mock_profile_query
        return MagicMock()
    db.execute = db_execute

    from app.schemas.fallback import DatabaseConnectionDetails
    conn_details = DatabaseConnectionDetails(
        db_type="sqlite",
        database="test_custom.db"
    )

    mock_conn = MagicMock()
    mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

    table_name = create_backup_table_for_request(
        request_id,
        "admin",
        "Notes",
        db,
        schema_name=None,
        table_name="custom_table",
        connection_details=conn_details
    )

    assert table_name == "custom_table"
    assert request.request_status == "APPROVED"
    assert job.status == "COMPLETED"
    mock_engine.assert_called_once_with("sqlite:///test_custom.db")
    exec_calls = [str(call[0][0]) for call in mock_conn.execute.call_args_list]
    assert any("CREATE TABLE" in c for c in exec_calls)


# ==========================================
# 4. FASTAPI ROUTE INTEGRATION TESTS
# ==========================================

client = TestClient(app)

def test_route_list_fallback_requests():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        requests_mock = [
            SchemaFallbackRequest(
                request_id=uuid.uuid4(),
                job_id=uuid.uuid4(),
                artifact_id=uuid.uuid4(),
                request_reason="CRITICAL_DRIFT",
                request_status="PENDING",
                created_at=datetime.utcnow()
            )
        ]
        mock_results = MagicMock()
        mock_results.scalars.return_value.all.return_value = requests_mock
        db.execute.return_value = mock_results

        response = client.get("/schema-fallbacks?status=PENDING")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["request_reason"] == "CRITICAL_DRIFT"
        assert data[0]["request_status"] == "PENDING"
    finally:
        app.dependency_overrides.clear()


@patch("app.api.fallback_routes.create_backup_table_for_request")
def test_route_approve_request(mock_approve):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    mock_approve.return_value = "raw_landing.backup_job_123"
    try:
        request_id = str(uuid.uuid4())
        response = client.post(
            f"/schema-fallbacks/{request_id}/approve",
            json={"approved_by": "admin", "review_notes": "Looks good"}
        )
        assert response.status_code == 200
        assert response.json()["backup_table_name"] == "raw_landing.backup_job_123"
        mock_approve.assert_called_once_with(
            request_id=uuid.UUID(request_id),
            approved_by="admin",
            review_notes="Looks good",
            db=db,
            schema_name="raw_landing",
            table_name=None,
            connection_details=None
        )
    finally:
        app.dependency_overrides.clear()


@patch("app.api.fallback_routes.reject_fallback_request")
def test_route_reject_request(mock_reject):
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    try:
        request_id = str(uuid.uuid4())
        response = client.post(
            f"/schema-fallbacks/{request_id}/reject",
            json={"rejected_by": "admin", "review_notes": "Not allowed"}
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Fallback request rejected successfully"
        mock_reject.assert_called_once_with(
            request_id=uuid.UUID(request_id),
            rejected_by="admin",
            review_notes="Not allowed",
            db=db
        )
    finally:
        app.dependency_overrides.clear()
