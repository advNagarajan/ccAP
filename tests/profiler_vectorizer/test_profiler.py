import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import uuid4

from app.models.domain.dataset import Dataset
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.artifact_record import ArtifactRecord
from app.services.metadata_service import (
    extract_metadata,
    generate_embedding_optimized_text,
    generate_llm_optimized_json
)
from workers.vectorizers.metadata_vectorizer.processor import sync_metadata_vector


def test_profiler_type_inference():
    # Dataset containing multiple types in columns
    records = [
        {"id": 1, "name": "Alice", "age": 30, "is_active": True, "joined_at": "2026-06-01T12:00:00Z"},
        {"id": 2, "name": "Bob", "age": 25, "is_active": False, "joined_at": "2026-06-02T13:00:00Z"},
        {"id": 3, "name": "Charlie", "age": 35, "is_active": True, "joined_at": "2026-06-03T14:00:00Z"}
    ]
    dataset = Dataset(records=records, source_type="GCS", format_type="JSON")
    metadata = extract_metadata(dataset, connector_metadata={"object_name": "test_users"})

    # Check columns type inferences
    columns = {col.name: col for col in metadata.columns}
    assert columns["id"].observed_types == ["int"]
    assert columns["name"].observed_types == ["str"]
    assert columns["age"].observed_types == ["int"]
    assert columns["is_active"].observed_types == ["bool"]
    assert columns["joined_at"].observed_types == ["str"]


def test_profiler_statistics_aggregation():
    records = [
        {"score": 90.5, "comments": "Good", "extra": None},
        {"score": 85.0, "comments": None, "extra": "A"},
        {"score": 95.0, "comments": "Excellent", "extra": None}
    ]
    dataset = Dataset(records=records, source_type="GCS", format_type="JSON")
    metadata = extract_metadata(dataset, connector_metadata={"object_name": "test_scores"})

    # Row/Col stats
    assert metadata.statistics.row_count == 3
    assert metadata.statistics.column_count == 3

    columns = {col.name: col for col in metadata.columns}
    # Null counts
    assert columns["score"].null_count == 0
    assert columns["comments"].null_count == 1
    assert columns["extra"].null_count == 2

    # Presence percentage
    assert columns["score"].presence_percentage == 100.0
    assert columns["comments"].presence_percentage == pytest.approx(66.66, 0.1)
    assert columns["extra"].presence_percentage == pytest.approx(33.33, 0.1)

    # Numeric stats
    assert columns["score"].numeric_statistics is not None
    assert columns["score"].numeric_statistics.mean == 90.16666666666667
    assert columns["score"].numeric_statistics.median == 90.5


def test_profiler_edge_cases():
    # 1. Empty dataset
    dataset_empty = Dataset(records=[], source_type="GCS", format_type="JSON")
    meta_empty = extract_metadata(dataset_empty, connector_metadata={})
    assert meta_empty.statistics.row_count == 0
    assert meta_empty.statistics.column_count == 0

    # 2. Pure Nulls
    records_nulls = [{"age": None}, {"age": None}]
    dataset_nulls = Dataset(records=records_nulls, source_type="GCS", format_type="JSON")
    meta_nulls = extract_metadata(dataset_nulls, connector_metadata={})
    assert meta_nulls.columns[0].null_count == 2
    assert meta_nulls.columns[0].observed_types == []

    # 3. Mixed Types in one column
    records_mixed = [{"val": 10}, {"val": "hello"}, {"val": 15.5}]
    dataset_mixed = Dataset(records=records_mixed, source_type="GCS", format_type="JSON")
    meta_mixed = extract_metadata(dataset_mixed, connector_metadata={})
    assert sorted(meta_mixed.columns[0].observed_types) == ["float", "int", "str"]


def test_passport_and_llm_json_optimization():
    records = [{"id": 1, "name": "Alice"}]
    dataset = Dataset(records=records, source_type="GCS", format_type="JSON")
    metadata = extract_metadata(dataset, connector_metadata={"object_name": "users_data"})

    # Test passport text generation
    raw_dict = metadata.to_dict() if hasattr(metadata, "to_dict") else {
        "statistics": {"row_count": 1, "column_count": 2},
        "columns": [
            {"name": "id", "observed_types": ["int"], "is_unique": True, "presence_percentage": 100.0},
            {"name": "name", "observed_types": ["str"], "is_unique": False, "presence_percentage": 100.0}
        ],
        "connector_metadata": {"object_name": "users_data"}
    }
    
    passport = generate_embedding_optimized_text(raw_dict)
    assert "users data" in passport.lower()
    assert "column name: id, data type: int (unique identifier) (present in 100% of records)" in passport.lower()

    # Test LLM JSON optimizer
    optimized = generate_llm_optimized_json(raw_dict)
    assert "statistics" in optimized
    assert "columns" in optimized
    assert optimized["statistics"]["row_count"] == 1


@pytest.mark.anyio
@patch("workers.vectorizers.metadata_vectorizer.processor.get_vector_embedding", new_callable=AsyncMock)
@patch("workers.vectorizers.metadata_vectorizer.processor.publish_metadata_vectorized")
async def test_sync_metadata_vector_skipped(mock_publish, mock_get_embedding):
    # Tests that vectorization is skipped if predefined_target_ids matches setup
    db_session = MagicMock()
    
    # Setup mock job, source, and config
    mock_job = MagicMock()
    mock_job.source_id = uuid4()
    mock_source = MagicMock()
    mock_source.config_id = uuid4()
    mock_config = MagicMock()
    mock_config.config_content = {
        "predefined_target_ids": [str(uuid4())]
    }
    
    db_session.get.side_effect = lambda model, uuid_val: {
        MetadataProfile: MagicMock(),
        Job: mock_job,
        Source: mock_source,
        ProcessingConfiguration: mock_config
    }.get(model)

    await sync_metadata_vector(
        job_id=str(uuid4()),
        artifact_id=str(uuid4()),
        metadata_profile_id=str(uuid4()),
        db=db_session
    )

    # Embedding provider should NOT be queried
    mock_get_embedding.assert_not_called()
    # Event should be published directly
    mock_publish.assert_called_once()


@pytest.mark.anyio
@patch("workers.vectorizers.metadata_vectorizer.processor.get_vector_embedding", new_callable=AsyncMock)
@patch("workers.vectorizers.metadata_vectorizer.processor.publish_metadata_vectorized")
async def test_sync_metadata_vector_execution(mock_publish, mock_get_embedding):
    db_session = MagicMock()
    
    # Setup mock profile
    mock_profile = MagicMock()
    mock_profile.embedding_optimized_text = "optimized passport text"
    
    db_session.get.side_effect = lambda model, uuid_val: {
        MetadataProfile: mock_profile,
        Job: None # Job is None to trigger the standard embedding route
    }.get(model)

    mock_get_embedding.return_value = [0.1, 0.2, 0.3]

    await sync_metadata_vector(
        job_id=str(uuid4()),
        artifact_id=str(uuid4()),
        metadata_profile_id=str(uuid4()),
        db=db_session
    )

    mock_get_embedding.assert_called_once_with("optimized passport text")
    assert mock_profile.source_embedding == [0.1, 0.2, 0.3]
    assert db_session.commit.call_count >= 1
    mock_publish.assert_called_once()
