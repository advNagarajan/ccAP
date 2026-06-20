import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import pytest
import json
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.target_catalog import TargetCatalog
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_fallback_request import SchemaFallbackRequest
from app.models.db.job import Job
from app.models.db.source import Source

from app.api.configuration_routes import validate_predefined_targets
from workers.vectorizers.metadata_vectorizer.processor import sync_metadata_vector
from workers.inference.processor import infer_target_landing_zone
from workers.validation.processor import process_schema_validation
from workers.drift.processor import process_schema_drift
from app.core.settings import settings


# 1. API Verification Tests
def test_validate_predefined_targets_invalid_type():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        validate_predefined_targets({"predefined_target_ids": "not-a-list"}, db)
    assert exc.value.status_code == 400
    assert "must be a list" in exc.value.detail


def test_validate_predefined_targets_invalid_uuid():
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        validate_predefined_targets({"predefined_target_ids": ["not-a-uuid"]}, db)
    assert exc.value.status_code == 400
    assert "Invalid UUID format" in exc.value.detail


def test_validate_predefined_targets_missing_catalog_item():
    db = MagicMock()
    db.get.return_value = None  # Pretend target doesn't exist
    missing_id = str(uuid.uuid4())
    with pytest.raises(HTTPException) as exc:
        validate_predefined_targets({"predefined_target_ids": [missing_id]}, db)
    assert exc.value.status_code == 400
    assert "do not exist in Target Catalog" in exc.value.detail


def test_validate_predefined_targets_success():
    db = MagicMock()
    db.get.return_value = TargetCatalog(target_id=uuid.uuid4())
    valid_id = str(uuid.uuid4())
    # Should not raise exception
    validate_predefined_targets({"predefined_target_ids": [valid_id]}, db)


# 2. Metadata Vectorizer Bypass Tests
@pytest.mark.anyio
async def test_metadata_vectorizer_bypass():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        embedding_optimized_text="test text",
        source_embedding=None
    )

    job = Job(job_id=uuid.UUID(job_id), source_id=uuid.UUID(source_id))
    source = Source(source_id=uuid.UUID(source_id), config_id=uuid.UUID(config_id))
    config = ProcessingConfiguration(
        config_id=uuid.UUID(config_id),
        config_content={"predefined_target_ids": [str(target_id)]}
    )

    def db_get(model, ident):
        return {
            MetadataProfile: profile,
            Job: job,
            Source: source,
            ProcessingConfiguration: config
        }.get(model)
    db.get = db_get

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.vectorizers.metadata_vectorizer.processor.start_stage", return_value=mock_stage) as mock_start, \
         patch("workers.vectorizers.metadata_vectorizer.processor.complete_stage") as mock_complete, \
         patch("workers.vectorizers.metadata_vectorizer.processor.publish_metadata_vectorized") as mock_publish, \
         patch("workers.vectorizers.metadata_vectorizer.processor.get_vector_embedding") as mock_embedding:

        await sync_metadata_vector(job_id, artifact_id, profile_id, db)

        # Embedding API should NOT have been called
        mock_embedding.assert_not_called()
        # Stage completed as SKIPPED
        mock_complete.assert_called_once()
        details_arg = mock_complete.call_args[0][2] if len(mock_complete.call_args[0]) > 2 else mock_complete.call_args[1].get("details")
        assert details_arg["status"] == "SKIPPED"
        # Event published
        mock_publish.assert_called_once()


# 3. Target Inference Tests
@pytest.mark.anyio
async def test_target_inference_predefined_single():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={"columns": []},
        source_embedding=None  # Skips vectorization
    )

    job = Job(job_id=uuid.UUID(job_id), source_id=uuid.UUID(source_id))
    source = Source(source_id=uuid.UUID(source_id), config_id=uuid.UUID(config_id))
    config = ProcessingConfiguration(
        config_id=uuid.UUID(config_id),
        config_content={"predefined_target_ids": [target_id]}
    )
    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        schema_definition={"fields": []}
    )

    # Mock DB lookups
    def db_get(model, ident):
        if model == TargetCatalog and ident == uuid.UUID(target_id):
            return target
        return {
            MetadataProfile: profile,
            Job: job,
            Source: source,
            ProcessingConfiguration: config
        }.get(model)
    db.get = db_get

    # Mock DB query
    def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "target_catalog" in stmt_str or "targets" in stmt_str:
            res.scalars.return_value.all.return_value = [target]
            res.all.return_value = [(target, 1.0)]
        elif "landing_inferences" in stmt_str:
            res.scalar_one_or_none.return_value = None
        return res
    db.execute = mock_execute

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate_response.return_value = json.dumps({
        "selected_target_id": target_id,
        "confidence_score": 0.55,  # Low score, but overridden by predefined single
        "reasoning": "Selected predefined target",
        "column_mapping": {},
        "unmapped_source_columns": [],
        "missing_target_columns": []
    })

    with patch("workers.inference.processor.start_stage", return_value=mock_stage), \
         patch("workers.inference.processor.complete_stage") as mock_complete, \
         patch("workers.inference.processor.get_llm_provider", return_value=mock_llm_provider), \
         patch("workers.inference.processor.publish_target_inferred"):

        await infer_target_landing_zone(job_id, artifact_id, profile_id, db)

        # Retrieve saved inference
        db_calls = db.add.call_args_list
        assert len(db_calls) > 0
        inference_obj = db_calls[0][0][0]
        # Assert confidence was overridden to 1.0 and review is False
        assert inference_obj.confidence_score == 1.0
        assert inference_obj.requires_review is False


@pytest.mark.anyio
async def test_target_inference_predefined_over_limit():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={"columns": []},
        source_embedding=[0.1] * 768  # Necessary for semantic search
    )

    job = Job(job_id=uuid.UUID(job_id), source_id=uuid.UUID(source_id))
    source = Source(source_id=uuid.UUID(source_id), config_id=uuid.UUID(config_id))
    # Exceed limit (which is 7 by default)
    config = ProcessingConfiguration(
        config_id=uuid.UUID(config_id),
        config_content={"predefined_target_ids": [str(uuid.uuid4())] * 10}
    )

    def db_get(model, ident):
        return {
            MetadataProfile: profile,
            Job: job,
            Source: source,
            ProcessingConfiguration: config
        }.get(model)
    db.get = db_get

    def mock_execute(stmt):
        stmt_str = str(stmt).lower()
        res = MagicMock()
        if "landing_inferences" in stmt_str:
            res.scalar_one_or_none.return_value = None
        else:
            res.all.return_value = []
        return res
    db.execute = MagicMock(side_effect=mock_execute)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    mock_llm_provider = AsyncMock()
    mock_llm_provider.generate_response.return_value = json.dumps({
        "selected_target_id": None,
        "confidence_score": 0.0,
        "reasoning": "Over limit fallback",
        "column_mapping": {},
        "unmapped_source_columns": [],
        "missing_target_columns": []
    })

    with patch("workers.inference.processor.start_stage", return_value=mock_stage), \
         patch("workers.inference.processor.complete_stage"), \
         patch("workers.inference.processor.get_llm_provider", return_value=mock_llm_provider), \
         patch("workers.inference.processor.publish_target_inferred"):

        await infer_target_landing_zone(job_id, artifact_id, profile_id, db)

        # Verify semantic search query was executed
        assert db.execute.called
        calls = [str(call[0][0]).lower() for call in db.execute.call_args_list]
        assert any("embedding" in c or "similarity" in c or "<->" in c for c in calls)


# 4. Schema Validation Custom Threshold Tests
def test_schema_validation_custom_threshold():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(profile_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "user_id", "observed_types": ["int"]},
                {"name": "unmapped_col", "observed_types": ["str"]}
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
        column_mapping={"user_id": "id", "unmapped_col": None},
        unmapped_source_columns=["unmapped_col"],
        missing_target_columns=[]
    )

    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"}
            ]
        }
    )

    job = Job(job_id=uuid.UUID(job_id), source_id=uuid.UUID(source_id))
    source = Source(source_id=uuid.UUID(source_id), config_id=uuid.UUID(config_id))
    # Custom validation threshold of 0.40. Since coverage is 50%, 0.50 >= 0.40, so status should be PASSED instead of WARNING!
    config = ProcessingConfiguration(
        config_id=uuid.UUID(config_id),
        config_content={"validation_thresholds": {"warning_threshold": 0.40}}
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    db.get = lambda model, ident: {
        LandingInference: inference,
        MetadataProfile: profile,
        TargetCatalog: target,
        Job: job,
        Source: source,
        ProcessingConfiguration: config
    }.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.validation.processor.start_stage", return_value=mock_stage), \
         patch("workers.validation.processor.complete_stage"), \
         patch("workers.validation.processor.publish_schema_validated"):

        val_record = process_schema_validation(job_id, artifact_id, profile_id, inference_id, db)
        assert val_record.validation_status == "PASSED"


# 5. Schema Drift Custom Threshold Tests
def test_schema_drift_custom_thresholds():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    validation_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())
    config_id = str(uuid.uuid4())

    profile = MetadataProfile(
        metadata_profile_id=uuid.UUID(str(uuid.uuid4())),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_json={
            "columns": [
                {"name": "id", "observed_types": ["int"]},
                {"name": "new_column", "observed_types": ["str"]}  # 1 new column drift
            ]
        }
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        target_id=uuid.UUID(target_id),
        column_mapping={"id": "id", "new_column": None}
    )

    # Target has 3 columns. Drift score = 1 / 3 = 33.3%
    target = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER"},
                {"name": "name", "type": "VARCHAR"},
                {"name": "email", "type": "VARCHAR"}
            ]
        }
    )

    val_record = SchemaValidation(
        validation_id=uuid.UUID(validation_id),
        job_id=uuid.UUID(job_id),
        inference_id=uuid.UUID(inference_id),
        target_id=uuid.UUID(target_id)
    )

    job = Job(job_id=uuid.UUID(job_id), source_id=uuid.UUID(source_id))
    source = Source(source_id=uuid.UUID(source_id), config_id=uuid.UUID(config_id))
    # Override drift thresholds: warning=10%, critical=30%
    # With a drift score of 33.3%, this should trigger CRITICAL_DRIFT
    config = ProcessingConfiguration(
        config_id=uuid.UUID(config_id),
        config_content={"drift_thresholds": {"warning_threshold": 10.0, "critical_threshold": 30.0}}
    )

    db.execute.return_value.scalar_one_or_none.return_value = None
    db.get = lambda model, ident: {
        SchemaValidation: val_record,
        LandingInference: inference,
        MetadataProfile: profile,
        TargetCatalog: target,
        Job: job,
        Source: source,
        ProcessingConfiguration: config
    }.get(model)

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.drift.processor.start_stage", return_value=mock_stage), \
         patch("workers.drift.processor.complete_stage"), \
         patch("workers.drift.processor.publish_drift_detected"):

        drift_record = process_schema_drift(job_id, artifact_id, validation_id, db)
        assert drift_record.drift_status == "CRITICAL_DRIFT"
