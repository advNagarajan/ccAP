import uuid
import pytest
from unittest.mock import MagicMock, patch

from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.job import Job
from workers.validation.processor import process_schema_validation

def test_validation_passed():
    # 1. Setup mocks
    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["int"]},
                {"name": "user_email", "observed_types": ["str"]}
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.UUID(profile_id),
        target_id=uuid.UUID(target_id),
        confidence_score=0.95,
        column_mapping={"user_id": "id", "user_email": "email"},
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="Matches perfectly"
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        target_type="POSTGRESQL",
        connection_details={},
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"},
                {"name": "email", "type": "VARCHAR"}
            ]
        }
    )

    def db_get(model_class, ident):
        if model_class == LandingInference:
            return inference
        if model_class == MetadataProfile:
            return profile
        if model_class == TargetCatalog:
            return target
        if model_class == Job:
            return Job(job_id=uuid.UUID(job_id), status="RUNNING")
        return None

    db.get = db_get

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    # Stub validation record instantiation
    created_records = []
    def db_add(instance):
        if isinstance(instance, SchemaValidation):
            if not getattr(instance, "validation_id", None):
                instance.validation_id = uuid.uuid4()
            created_records.append(instance)
    db.add = db_add

    with patch("workers.validation.processor.start_stage", return_value=mock_stage) as mock_start, \
         patch("workers.validation.processor.complete_stage") as mock_complete, \
         patch("workers.validation.processor.publish_schema_validated") as mock_publish:

        # Run validation
        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

        # Assertions
        assert val_record.validation_status == "PASSED"
        assert val_record.coverage_percentage == 100.0
        assert val_record.target_match_percentage == 100.0
        assert val_record.mapped_column_count == 2
        assert val_record.source_column_count == 2
        assert val_record.target_column_count == 2
        
        report = val_record.report_json
        assert report["report_version"] == "1.0"
        assert len(report["invalid_mappings"]) == 0
        assert len(report["datatype_issues"]) == 0

        mock_complete.assert_called_once()
        mock_publish.assert_called_once_with(
            job_id=job_id,
            artifact_id=artifact_id,
            inference_id=inference_id,
            validation_id=str(val_record.validation_id),
            validation_status="PASSED"
        )


def test_validation_warning_type_mismatch():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["str"]},  # str instead of int
                {"name": "user_email", "observed_types": ["str"]}
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.UUID(profile_id),
        target_id=uuid.UUID(target_id),
        confidence_score=0.95,
        column_mapping={"user_id": "id", "user_email": "email"},
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="Type mismatch on ID"
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        target_type="POSTGRESQL",
        connection_details={},
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"},
                {"name": "email", "type": "VARCHAR"}
            ]
        }
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    db.get = lambda model, ident: {LandingInference: inference, MetadataProfile: profile, TargetCatalog: target, Job: job}.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.validation.processor.start_stage", return_value=mock_stage), \
         patch("workers.validation.processor.complete_stage") as mock_complete, \
         patch("workers.validation.processor.publish_schema_validated"):

        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

        assert val_record.validation_status == "WARNING"
        assert len(val_record.report_json["datatype_issues"]) == 1
        assert val_record.report_json["datatype_issues"][0]["source_column"] == "user_id"
        assert val_record.report_json["datatype_issues"][0]["severity"] == "WARNING"


def test_validation_warning_low_coverage():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["int"]},
                {"name": "user_phone", "observed_types": ["str"]}  # Unmapped
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.UUID(profile_id),
        target_id=uuid.UUID(target_id),
        confidence_score=0.95,
        column_mapping={"user_id": "id", "user_phone": None},
        unmapped_source_columns=["user_phone"],
        missing_target_columns=["email"],
        reasoning="Partial match"
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        target_type="POSTGRESQL",
        connection_details={},
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"},
                {"name": "email", "type": "VARCHAR"}
            ]
        }
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    db.get = lambda model, ident: {LandingInference: inference, MetadataProfile: profile, TargetCatalog: target, Job: job}.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.validation.processor.start_stage", return_value=mock_stage), \
         patch("workers.validation.processor.complete_stage"), \
         patch("workers.validation.processor.publish_schema_validated"), \
         patch("workers.validation.processor.settings") as mock_settings:
        
        mock_settings.VALIDATION_WARNING_THRESHOLD = 0.90  # 90%

        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

        assert val_record.validation_status == "WARNING"
        assert val_record.coverage_percentage == 50.0  # 1/2 columns mapped
        assert val_record.target_match_percentage == 50.0  # 1/2 target fields satisfied


def test_validation_failed_invalid_mapping():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["int"]}
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.UUID(profile_id),
        target_id=uuid.UUID(target_id),
        confidence_score=0.95,
        column_mapping={"nonexistent_source_column": "id"},  # Invalid source column (results in FAILED validation status)
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="Bad mapping"
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        target_type="POSTGRESQL",
        connection_details={},
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"}
            ]
        }
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    db.get = lambda model, ident: {LandingInference: inference, MetadataProfile: profile, TargetCatalog: target, Job: job}.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.validation.processor.start_stage", return_value=mock_stage), \
         patch("workers.validation.processor.complete_stage"), \
         patch("workers.validation.processor.publish_schema_validated"):

        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

        assert val_record.validation_status == "FAILED"
        assert len(val_record.report_json["invalid_mappings"]) == 1
        assert val_record.report_json["invalid_mappings"][0]["severity"] == "ERROR"


def test_validation_skipped():
    db = MagicMock()
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
        target_id=None,  # Skipped
        confidence_score=0.0,
        column_mapping={},
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="No target matches"
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    job = Job(job_id=uuid.UUID(job_id), status="RUNNING")
    db.get = lambda model, ident: {LandingInference: inference, MetadataProfile: profile, Job: job}.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.validation.processor.start_stage", return_value=mock_stage), \
         patch("workers.validation.processor.complete_stage") as mock_complete, \
         patch("workers.validation.processor.publish_schema_validated") as mock_publish, \
         patch("workers.validation.processor.publish_fallback_requested") as mock_fallback:

        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)

        assert val_record.validation_status == "SKIPPED"
        assert val_record.coverage_percentage == 0.0
        assert val_record.target_match_percentage == 0.0
        mock_fallback.assert_called_once()
        mock_publish.assert_not_called()
