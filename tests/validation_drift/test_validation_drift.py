import pytest
from unittest.mock import MagicMock, patch, ANY
from uuid import uuid4

from app.services.validation_service import compute_schema_validation
from app.services.drift_service import compute_schema_drift, normalize_type_token
from workers.validation.processor import process_schema_validation
from workers.drift.processor import process_schema_drift
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_fallback_request import SchemaFallbackRequest


def test_normalize_type_token():
    assert normalize_type_token("character varying") == "str"
    assert normalize_type_token("bigint") == "int"
    assert normalize_type_token("boolean") == "bool"
    assert normalize_type_token("timestamp with time zone") == "datetime"
    assert normalize_type_token("UNKNOWN_TYPE") == "unknown_type"


def test_schema_validation_perfect_match():
    metadata_json = {
        "columns": [
            {"name": "id", "observed_types": ["int"]},
            {"name": "name", "observed_types": ["str"]}
        ]
    }
    schema_definition = {
        "id": "INTEGER",
        "name": "VARCHAR(255)"
    }
    column_mapping = {
        "id": "id",
        "name": "name"
    }

    result = compute_schema_validation(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        unmapped_source_columns=[],
        missing_target_columns=[],
        warning_threshold=0.80
    )

    assert result["validation_status"] == "PASSED"
    assert result["coverage_percentage"] == 100.0
    assert result["target_match_percentage"] == 100.0


def test_schema_validation_warning_threshold():
    metadata_json = {
        "columns": [
            {"name": "id", "observed_types": ["int"]},
            {"name": "name", "observed_types": ["str"]},
            {"name": "unmapped_col", "observed_types": ["str"]}
        ]
    }
    schema_definition = {
        "id": "INTEGER",
        "name": "VARCHAR(255)"
    }
    # Coverage will be 2/3 = 66.67%
    column_mapping = {
        "id": "id",
        "name": "name",
        "unmapped_col": None
    }

    # Case A: warning_threshold = 0.50 (66.67% is above threshold -> PASSED)
    result_passed = compute_schema_validation(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        unmapped_source_columns=["unmapped_col"],
        missing_target_columns=[],
        warning_threshold=0.50
    )
    assert result_passed["validation_status"] == "PASSED"

    # Case B: warning_threshold = 0.80 (66.67% is below threshold -> WARNING)
    result_warning = compute_schema_validation(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        unmapped_source_columns=["unmapped_col"],
        missing_target_columns=[],
        warning_threshold=0.80
    )
    assert result_warning["validation_status"] == "WARNING"


def test_schema_drift_computation():
    metadata_json = {
        "columns": [
            {"name": "id", "observed_types": ["int"]},
            {"name": "full_name", "observed_types": ["str"]}, # Renamed from name
            {"name": "new_feature", "observed_types": ["bool"]} # Added column
        ]
    }
    schema_definition = {
        "id": "INTEGER",
        "name": "VARCHAR(255)",
        "removed_col": "DATE" # Removed column
    }
    # 3 total target columns: id, name, removed_col
    # Renamed: name -> full_name (1)
    # Added: new_feature (1)
    # Removed: removed_col (1)
    # Drift Score: 3 / 3 = 100%
    column_mapping = {
        "id": "id",
        "full_name": "name",
        "new_feature": None
    }

    result = compute_schema_drift(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        warning_threshold=20.0,
        critical_threshold=50.0
    )

    assert result["drift_status"] == "CRITICAL_DRIFT"
    assert result["drift_score"] == 100.0
    assert "new_feature" in result["drift_summary"]["new_columns"]
    assert "removed_col" in result["drift_summary"]["removed_columns"]
    assert len(result["drift_summary"]["renamed_columns"]) == 1
    assert result["drift_summary"]["renamed_columns"][0]["source_column"] == "full_name"


def test_schema_drift_threshold_boundaries():
    metadata_json = {
        "columns": [
            {"name": "id", "observed_types": ["int"]},
            {"name": "name", "observed_types": ["str"]},
            {"name": "extra", "observed_types": ["str"]}
        ]
    }
    schema_definition = {
        "id": "INTEGER",
        "name": "VARCHAR(255)",
        "col3": "INTEGER",
        "col4": "INTEGER",
        "col5": "INTEGER"
    }
    # 5 total target columns.
    # Added: extra (1)
    # Removed: col3, col4, col5 (3)
    # Total changes: 4. Drift score: 4/5 = 80%.
    column_mapping = {
        "id": "id",
        "name": "name",
        "extra": None
    }

    # Case A: 80% is above critical_threshold (50%) -> CRITICAL_DRIFT
    result_crit = compute_schema_drift(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        warning_threshold=20.0,
        critical_threshold=50.0
    )
    assert result_crit["drift_status"] == "CRITICAL_DRIFT"

    # Case B: critical_threshold = 90% (80% is <= 90% and > 20% -> DRIFTED)
    result_drifted = compute_schema_drift(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        warning_threshold=20.0,
        critical_threshold=90.0
    )
    assert result_drifted["drift_status"] == "DRIFTED"


@patch("workers.validation.processor.publish_schema_validated")
def test_validation_worker_pipeline(mock_publish):
    # Setup mocks
    db_session = MagicMock()

    mock_job = MagicMock()
    mock_job.source_id = uuid4()
    db_session.get.return_value = mock_job

    mock_profile = MagicMock()
    mock_profile.metadata_json = {
        "columns": [{"name": "id", "observed_types": ["int"]}]
    }

    # Mock DB Query results
    db_session.execute.return_value.scalar_one_or_none.side_effect = [
        None, # SchemaValidation row lookup
        MagicMock(schema_definition={"id": "INTEGER"}), # Target catalog row
        MagicMock(column_mapping={"id": "id"}, unmapped_source_columns=[], missing_target_columns=[]) # Inference row
    ]
    mock_inference = MagicMock()
    mock_inference.target_id = uuid4()
    mock_inference.column_mapping = {"id": "id"}
    mock_inference.unmapped_source_columns = []
    mock_inference.missing_target_columns = []

    mock_target = MagicMock()
    mock_target.schema_definition = {"id": "INTEGER"}

    # Define db_session.get side effect properly mapping model classes to mocks
    db_session.get.side_effect = lambda model, val: {
        Job: mock_job,
        LandingInference: mock_inference,
        MetadataProfile: mock_profile,
        TargetCatalog: mock_target,
        Source: None,
        ProcessingConfiguration: None
    }.get(model)

    process_schema_validation(
        job_id=str(uuid4()),
        artifact_id=str(uuid4()),
        metadata_profile_id=str(uuid4()),
        inference_id=str(uuid4()),
        db=db_session
    )

    assert db_session.add.call_count >= 1
    db_session.commit.assert_called()
    mock_publish.assert_called_once()


def test_schema_validation_compatibility_warnings():
    # Test float mapped to INTEGER (causes type conversion warning/incompatibility)
    metadata_json = {
        "columns": [{"name": "price", "observed_types": ["float"]}]
    }
    schema_definition = {"id": "INTEGER"}
    column_mapping = {"price": "id"}
    
    result = compute_schema_validation(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        unmapped_source_columns=[],
        missing_target_columns=[],
        warning_threshold=0.80
    )
    
    assert result["validation_status"] == "WARNING"
    assert len(result["report_json"]["datatype_issues"]) == 1
    assert "Type conversion warning" in result["report_json"]["datatype_issues"][0]["reason"]


def test_schema_drift_empty_target_catalog():
    # Target catalog is completely empty
    metadata_json = {
        "columns": [{"name": "id", "observed_types": ["int"]}]
    }
    schema_definition = {}
    column_mapping = {"id": None}
    
    result = compute_schema_drift(
        metadata_json=metadata_json,
        schema_definition=schema_definition,
        column_mapping=column_mapping,
        warning_threshold=20.0,
        critical_threshold=50.0
    )
    
    assert result["drift_score"] == 100.0
    assert result["drift_status"] == "CRITICAL_DRIFT"
