import json
import uuid
import pytest
from datetime import datetime, UTC
from unittest.mock import MagicMock, patch

from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.artifact_record import ArtifactRecord
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.data_quality_job import DataQualityJob
from app.models.db.data_quality_report import DataQualityReport
from app.models.db.job_stage_history import JobStageHistory

from workers.quality.processor import process_data_quality
from workers.ingestion.processor import process_ingestion_requested


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    return db


def test_data_quality_all_rules_pass(mock_db):
    job_id = str(uuid.uuid4())
    parent_job_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    source = Source(source_id=uuid.UUID(source_id), source_type="GCS")
    config = ProcessingConfiguration(
        config_content={
            "data_quality_enabled": True,
            "data_quality_rules": [
                {
                    "type": "null_check",
                    "columns": ["id", "name"],
                    "allowed_null_ratio": 0.1,
                    "severity": "FAILED"
                },
                {
                    "type": "uniqueness_check",
                    "columns": ["id"],
                    "severity": "FAILED"
                },
                {
                    "type": "data_type_validity_check",
                    "columns": {"age": "int", "price": "float"},
                    "severity": "WARNING"
                },
                {
                    "type": "boundary_range_check",
                    "columns": {"age": {"min": 0, "max": 120}},
                    "severity": "FAILED"
                },
                {
                    "type": "regex_pattern_check",
                    "columns": {"email": "^\\S+@\\S+\\.\\S+$"},
                    "severity": "FAILED"
                },
                {
                    "type": "set_membership_check",
                    "columns": {"status": ["ACTIVE", "INACTIVE"]},
                    "severity": "WARNING"
                },
                {
                    "type": "freshness_check",
                    "column": "created_at",
                    "max_age_hours": 24.0,
                    "severity": "WARNING"
                },
                {
                    "type": "volume_change_check",
                    "max_change_percentage": 25.0,
                    "severity": "WARNING"
                }
            ]
        }
    )
    source.configuration = config

    artifact_record = ArtifactRecord(
        artifact_id=uuid.UUID(artifact_id),
        external_artifact_id="gcs://bucket/file.csv",
        artifact_name="file.csv",
        discovered_at=datetime.now(UTC),
        artifact_metadata={"bucket": "bucket", "object_name": "file.csv"}
    )

    def db_get(model_class, ident):
        if model_class == Job:
            return job
        if model_class == Source:
            return source
        if model_class == ArtifactRecord:
            return artifact_record
        return None
    mock_db.get = db_get

    # Mock connector and dataset
    mock_connector = MagicMock()
    mock_raw = MagicMock()
    mock_raw.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw

    mock_parser = MagicMock()
    mock_dataset = MagicMock()
    mock_dataset.records = [
        {"id": "1", "name": "Alice", "age": "30", "price": "12.50", "email": "alice@gmail.com", "status": "ACTIVE", "created_at": datetime.now(UTC).isoformat()},
        {"id": "2", "name": "Bob", "age": "25", "price": "100.00", "email": "bob@gmail.com", "status": "INACTIVE", "created_at": datetime.now(UTC).isoformat()}
    ]
    mock_parser.parse.return_value = mock_dataset

    created_reports = []
    def db_add(instance):
        if isinstance(instance, DataQualityReport):
            instance.report_id = uuid.uuid4()
            created_reports.append(instance)
    mock_db.add = db_add

    # Stub stage history functions
    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.quality.processor.CONNECTORS", {"GCS": mock_connector}), \
         patch("workers.quality.processor.PARSERS", {"CSV": mock_parser}), \
         patch("workers.quality.processor.start_stage", return_value=mock_stage), \
         patch("workers.quality.processor.complete_stage") as mock_complete:

        report = process_data_quality(job_id, parent_job_id, source_id, artifact_id, mock_db)

        assert report is not None
        assert report.status == "PASSED"
        assert report.rules_executed == 8
        assert report.rules_failed == 0

        report_json = report.report_json
        assert report_json["overall_status"] == "PASSED"
        assert report_json["total_rows"] == 2
        assert len(report_json["rules"]) == 8
        for r in report_json["rules"]:
            assert r["status"] == "PASSED"
            assert r["failure_count"] == 0


def test_data_quality_rules_failure(mock_db):
    job_id = str(uuid.uuid4())
    parent_job_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())

    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    source = Source(source_id=uuid.UUID(source_id), source_type="GCS")
    config = ProcessingConfiguration(
        config_content={
            "data_quality_enabled": True,
            "data_quality_rules": [
                {
                    "type": "null_check",
                    "columns": ["id", "email"],
                    "allowed_null_ratio": 0.05,
                    "severity": "FAILED"
                },
                {
                    "type": "uniqueness_check",
                    "columns": ["id"],
                    "severity": "WARNING"
                }
            ]
        }
    )
    source.configuration = config

    artifact_record = ArtifactRecord(
        artifact_id=uuid.UUID(artifact_id),
        external_artifact_id="gcs://bucket/file.csv",
        artifact_name="file.csv",
        discovered_at=datetime.now(UTC),
        artifact_metadata={"bucket": "bucket", "object_name": "file.csv"}
    )

    def db_get(model_class, ident):
        if model_class == Job:
            return job
        if model_class == Source:
            return source
        if model_class == ArtifactRecord:
            return artifact_record
        return None
    mock_db.get = db_get

    mock_connector = MagicMock()
    mock_raw = MagicMock()
    mock_raw.format_type = "CSV"
    mock_connector.extract_full.return_value = mock_raw

    mock_parser = MagicMock()
    mock_dataset = MagicMock()
    # 3 records:
    # - record 1: id=1, email=alice@gmail.com
    # - record 2: id=1 (duplicate), email=None (null email, exceeds 5% of 3)
    # - record 3: id=3, email=bob@gmail.com
    mock_dataset.records = [
        {"id": "1", "email": "alice@gmail.com"},
        {"id": "1", "email": None},
        {"id": "3", "email": "bob@gmail.com"}
    ]
    mock_parser.parse.return_value = mock_dataset

    # Setup mock stage
    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.quality.processor.CONNECTORS", {"GCS": mock_connector}), \
         patch("workers.quality.processor.PARSERS", {"CSV": mock_parser}), \
         patch("workers.quality.processor.start_stage", return_value=mock_stage), \
         patch("workers.quality.processor.complete_stage"):

        report = process_data_quality(job_id, parent_job_id, source_id, artifact_id, mock_db)

        # Status should be FAILED because the Null Check failed and has FAILED severity.
        assert report is not None
        assert report.status == "FAILED"
        assert report.rules_executed == 2
        assert report.rules_failed == 2

        report_json = report.report_json
        assert report_json["overall_status"] == "FAILED"
        
        # Null check should fail
        null_rule_res = next(r for r in report_json["rules"] if r["rule_type"] == "null_check")
        assert null_rule_res["status"] == "FAILED"
        assert null_rule_res["failure_count"] == 1

        # Uniqueness check should fail
        unique_rule_res = next(r for r in report_json["rules"] if r["rule_type"] == "uniqueness_check")
        assert unique_rule_res["status"] == "FAILED"
        assert unique_rule_res["failure_count"] == 1


@patch("app.pubsub.publisher.publish_quality_check_requested")
@patch("workers.ingestion.processor.publish_dataset_received")
@patch("workers.ingestion.processor.start_stage")
@patch("workers.ingestion.processor.complete_stage")
def test_ingestion_quality_check_trigger_lineage(mock_complete_stage, mock_start_stage, mock_publish_rec, mock_publish_dq, mock_db):
    # Setup parent job and artifact
    job_id = uuid.uuid4()
    source_id = uuid.uuid4()
    artifact_uuid = uuid.uuid4()

    job = Job(
        job_id=job_id,
        source_id=source_id,
        status="RUNNING",
        parent_job_id=None
    )

    source = Source(source_id=source_id, source_type="GCS")
    config = ProcessingConfiguration(
        config_content={"data_quality_enabled": True, "data_quality_rules": []}
    )
    source.configuration = config

    artifact_record = ArtifactRecord(
        artifact_id=artifact_uuid,
        external_artifact_id="gcs://bucket/file.csv",
        artifact_name="file.csv",
        discovered_at=datetime.now(UTC),
        artifact_metadata={"bucket": "bucket", "object_name": "file.csv"}
    )

    def db_get(model_class, ident):
        if model_class == Job:
            return job
        if model_class == Source:
            return source
        return None
    mock_db.get = db_get

    # Mock execute queries
    def mock_execute(stmt, *args, **kwargs):
        stmt_str = str(stmt).upper()
        res = MagicMock()
        if "ARTIFACT_RECORDS" in stmt_str:
            res.scalar_one_or_none.return_value = artifact_record
        elif "DATA_QUALITY_REPORTS" in stmt_str:
            res.scalars.return_value.first.return_value = None
        elif "DATA_QUALITY_JOBS" in stmt_str:
            res.scalar_one_or_none.return_value = None
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.first.return_value = None
        return res
    mock_db.execute.side_effect = mock_execute

    # Mock connector and parser
    mock_connector = MagicMock()
    domain_artifact = MagicMock()
    domain_artifact.external_id = "gcs://bucket/file.csv"
    domain_artifact.artifact_name = "file.csv"
    mock_connector.list_artifacts.return_value = [domain_artifact]
    mock_connector.get_unprocessed_artifacts.return_value = [domain_artifact]
    
    mock_raw = MagicMock()
    mock_raw.format_type = "CSV"
    mock_connector.extract_sample.return_value = mock_raw

    mock_parser = MagicMock()
    mock_dataset = MagicMock()
    mock_dataset.records = [{"id": "1"}]
    mock_parser.parse.return_value = mock_dataset

    with patch("workers.ingestion.processor.CONNECTORS", {"GCS": mock_connector}), \
         patch("workers.ingestion.processor.PARSERS", {"CSV": mock_parser}), \
         patch("workers.ingestion.processor.SessionLocal", return_value=mock_db):

        payload_bytes = json.dumps({"job_id": str(job_id), "force_dq": False}).encode("utf-8")
        process_ingestion_requested(payload_bytes)

        # Quality check should be published!
        mock_publish_dq.assert_called_once()


def test_gcs_sampling():
    from app.connectors.gcs_connector import GCSConnector
    from app.models.domain.artifact import Artifact
    from app.models.domain.raw_data import RawData

    connector = GCSConnector()
    source = Source(source_type="GCS", connection_details={"project_id": "test", "credentials_json": {"type": "service_account"}})
    artifact = Artifact(
        external_id="test.csv",
        artifact_name="test.csv",
        last_modified=datetime.now(UTC).isoformat(),
        metadata={"bucket": "my-bucket", "object_name": "test.csv"}
    )

    mock_parser = MagicMock()
    mock_dataset = MagicMock()
    # 4 records:
    mock_dataset.records = [
        {"id": "1", "name": "Alice"},
        {"id": "2", "name": "Bob"},
        {"id": "3", "name": "Charlie"},
        {"id": "4", "name": "Dave"}
    ]
    mock_parser.parse.return_value = mock_dataset

    mock_blob = MagicMock()
    mock_blob.download_as_text.return_value = "id,name\n1,Alice\n2,Bob\n3,Charlie\n4,Dave"
    
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch.object(GCSConnector, "_get_client", return_value=mock_client), \
         patch("app.parsers.registry.PARSERS", {"CSV": mock_parser}):

        # Run extract_full with 50% sampling
        raw_data = connector.extract_full(source, artifact, sample_ratio=0.5, random_sample=False)
        
        # Should parse full dataset first, sample 50% (k=2 records), and re-serialize to CSV
        assert raw_data is not None
        assert "Alice" in raw_data.content
        assert "Bob" in raw_data.content
        assert "Charlie" not in raw_data.content  # sampled 50% non-random, so only Alice and Bob
