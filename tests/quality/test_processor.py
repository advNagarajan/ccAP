import pytest
from datetime import datetime, UTC, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from workers.quality.processor import process_data_quality
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.artifact_record import ArtifactRecord
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.data_quality_report import DataQualityReport


def test_rule_null_check():
    # Helper to test null checks
    # Rules run inside process_data_quality. We can test them through mock processors
    # or isolate the database setup.
    pass


@pytest.fixture
def mock_db_setup():
    db = MagicMock()
    
    # Mock source configuration
    config = MagicMock()
    config.config_content = {
        "data_quality_sampling": {
            "sample_ratio": 1.0,
            "random_sample": False
        },
        "data_quality_rules": []
    }
    
    source = MagicMock()
    source.source_id = uuid4()
    source.source_type = "GCS"
    source.configuration = config
    
    artifact = MagicMock()
    artifact.artifact_id = uuid4()
    artifact.external_artifact_id = "test-gcs-path"
    artifact.artifact_name = "test-dataset"
    artifact.discovered_at = datetime.now(UTC)
    artifact.artifact_metadata = {}

    job = MagicMock()
    job.job_id = uuid4()
    job.source_id = source.source_id
    job.created_at = datetime.now(UTC)
    
    db.get.side_effect = lambda model, uuid_val: {
        Job: job,
        Source: source,
        ArtifactRecord: artifact
    }.get(model)

    return db, config, source, artifact, job


@pytest.mark.anyio
@patch("workers.quality.processor.CONNECTORS")
@patch("workers.quality.processor.PARSERS")
@patch("app.pubsub.publisher.publish_quality_check_completed")
async def test_process_quality_null_checks(mock_publish, mock_parsers, mock_connectors, mock_db_setup):
    db, config, source, artifact, job = mock_db_setup

    # Setup GCS extract and CSV parse
    mock_connector = MagicMock()
    mock_connectors.get.return_value = mock_connector
    mock_raw_data = MagicMock()
    mock_raw_data.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw_data

    mock_parser = MagicMock()
    mock_parsers.get.return_value = mock_parser
    
    mock_dataset = MagicMock()
    mock_dataset.records = [
        {"id": 1, "name": "Alice", "score": None},
        {"id": 2, "name": None, "score": 90.0},
        {"id": 3, "name": "Charlie", "score": None}
    ]
    mock_parser.parse.return_value = mock_dataset

    # Configure rule: null_check on name and score
    config.config_content["data_quality_rules"] = [
        {
            "type": "null_check",
            "columns": ["name"],
            "allowed_null_ratio": 0.40, # 1/3 = 33.3% -> PASSED
            "severity": "FAILED"
        },
        {
            "type": "null_check",
            "columns": ["score"],
            "allowed_null_ratio": 0.50, # 2/3 = 66.7% -> FAILED
            "severity": "WARNING"
        }
    ]

    report = process_data_quality(
        job_id=str(uuid4()),
        parent_job_id=str(uuid4()),
        source_id=str(source.source_id),
        artifact_id=str(artifact.artifact_id),
        db=db
    )

    assert report.status == "WARNING" # FAILED severity rule passed, WARNING severity rule failed
    assert report.rules_executed == 2
    assert report.rules_failed == 1
    assert report.report_json["rules"][0]["status"] == "PASSED"
    assert report.report_json["rules"][1]["status"] == "FAILED"


@pytest.mark.anyio
@patch("workers.quality.processor.CONNECTORS")
@patch("workers.quality.processor.PARSERS")
@patch("app.pubsub.publisher.publish_quality_check_completed")
async def test_process_quality_uniqueness_and_types(mock_publish, mock_parsers, mock_connectors, mock_db_setup):
    db, config, source, artifact, job = mock_db_setup

    mock_connector = MagicMock()
    mock_connectors.get.return_value = mock_connector
    mock_raw_data = MagicMock()
    mock_raw_data.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw_data

    mock_parser = MagicMock()
    mock_parsers.get.return_value = mock_parser
    
    mock_dataset = MagicMock()
    mock_dataset.records = [
        {"id": "1", "is_active": "yes", "value": "10.5"},
        {"id": "2", "is_active": "False", "value": "20"},
        {"id": "1", "is_active": "true", "value": "invalid_float"} # Duplicate ID, invalid float
    ]
    mock_parser.parse.return_value = mock_dataset

    config.config_content["data_quality_rules"] = [
        {
            "type": "uniqueness_check",
            "columns": ["id"],
            "severity": "FAILED"
        },
        {
            "type": "type_validity_check",
            "columns": {"is_active": "boolean", "value": "float"},
            "severity": "WARNING"
        }
    ]

    report = process_data_quality(
        job_id=str(uuid4()),
        parent_job_id=str(uuid4()),
        source_id=str(source.source_id),
        artifact_id=str(artifact.artifact_id),
        db=db
    )

    assert report.status == "FAILED" # ID duplicate triggers FAILED
    assert report.rules_failed == 2
    
    # Check type failures: is_active should pass (yes, False, true are booleans), value fails on invalid_float
    type_rule = report.report_json["rules"][1]
    assert type_rule["metrics"]["type_failures"]["is_active"] == 0
    assert type_rule["metrics"]["type_failures"]["value"] == 1


@pytest.mark.anyio
@patch("workers.quality.processor.CONNECTORS")
@patch("workers.quality.processor.PARSERS")
@patch("app.pubsub.publisher.publish_quality_check_completed")
async def test_process_quality_boundaries_and_regex(mock_publish, mock_parsers, mock_connectors, mock_db_setup):
    db, config, source, artifact, job = mock_db_setup

    mock_connector = MagicMock()
    mock_connectors.get.return_value = mock_connector
    mock_raw_data = MagicMock()
    mock_raw_data.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw_data

    mock_parser = MagicMock()
    mock_parsers.get.return_value = mock_parser
    
    mock_dataset = MagicMock()
    mock_dataset.records = [
        {"age": 25, "email": "valid@gmail.com"},
        {"age": -5, "email": "bad_email_format"}, # Age is out of bounds, email matches invalid regex
        {"age": "non_numeric", "email": "another@test.co"} # age is non_numeric
    ]
    mock_parser.parse.return_value = mock_dataset

    config.config_content["data_quality_rules"] = [
        {
            "type": "boundary_range_check",
            "columns": {"age": {"min": 0, "max": 120}},
            "severity": "FAILED"
        },
        {
            "type": "regex_pattern_check",
            "columns": {"email": "^\\S+@\\S+\\.\\S+$"},
            "severity": "FAILED"
        }
    ]

    report = process_data_quality(
        job_id=str(uuid4()),
        parent_job_id=str(uuid4()),
        source_id=str(source.source_id),
        artifact_id=str(artifact.artifact_id),
        db=db
    )

    assert report.status == "FAILED"
    boundary_rule = report.report_json["rules"][0]
    regex_rule = report.report_json["rules"][1]
    
    assert boundary_rule["metrics"]["boundary_failures"]["age"] == 2 # -5 and "non_numeric" fail
    assert regex_rule["metrics"]["regex_failures"]["email"] == 1 # "bad_email_format" fails


@pytest.mark.anyio
@patch("workers.quality.processor.CONNECTORS")
@patch("workers.quality.processor.PARSERS")
@patch("app.pubsub.publisher.publish_quality_check_completed")
async def test_process_quality_freshness_and_volume(mock_publish, mock_parsers, mock_connectors, mock_db_setup):
    db, config, source, artifact, job = mock_db_setup

    mock_connector = MagicMock()
    mock_connectors.get.return_value = mock_connector
    mock_raw_data = MagicMock()
    mock_raw_data.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw_data

    mock_parser = MagicMock()
    mock_parsers.get.return_value = mock_parser
    
    # 2 hours ago timestamp
    two_hours_ago = (datetime.now(UTC) - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    
    mock_dataset = MagicMock()
    mock_dataset.records = [
        {"updated_at": two_hours_ago, "status": "ACTIVE"},
        {"updated_at": None, "status": "INACTIVE"}
    ]
    mock_parser.parse.return_value = mock_dataset

    config.config_content["data_quality_rules"] = [
        {
            "type": "freshness_check",
            "column": "updated_at",
            "max_age_hours": 1.0, # Fail: newest record is 2 hours old, max allowed is 1
            "severity": "WARNING"
        },
        {
            "type": "set_membership_check",
            "columns": {"status": ["ACTIVE", "INACTIVE"]},
            "severity": "FAILED"
        },
        {
            "type": "volume_change_check",
            "max_change_percentage": 10.0,
            "severity": "WARNING"
        }
    ]

    # Mock previous row count query to return 0 to test division by zero protection
    db.execute.return_value.scalars.return_value.first.return_value = None

    report = process_data_quality(
        job_id=str(uuid4()),
        parent_job_id=str(uuid4()),
        source_id=str(source.source_id),
        artifact_id=str(artifact.artifact_id),
        db=db
    )

    assert report.status == "WARNING"
    assert report.report_json["rules"][0]["status"] == "FAILED" # Freshness failed
    assert report.report_json["rules"][1]["status"] == "PASSED" # Set membership passed
    assert report.report_json["rules"][2]["status"] == "PASSED" # Volume passed (prev count = 0, no change computed)
