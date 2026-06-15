import uuid
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.db.metadata_profile import MetadataProfile
from app.services.metadata_service import (
    generate_embedding_optimized_text,
    generate_llm_optimized_json,
    save_metadata
)
from workers.vectorizers.metadata_vectorizer.processor import sync_metadata_vector

# Sample raw metadata
SAMPLE_METADATA = {
    "statistics": {
        "row_count": 100,
        "column_count": 2
    },
    "columns": [
        {
            "name": "user_id",
            "observed_types": ["int"],
            "null_count": 0,
            "non_null_count": 100,
            "distinct_count": 100,
            "is_unique": True,
            "presence_percentage": 100.0,
            "sample_values": ["1", "2", "3"]
        },
        {
            "name": "user_email",
            "observed_types": ["str"],
            "null_count": 5,
            "non_null_count": 95,
            "distinct_count": 95,
            "is_unique": False,
            "presence_percentage": 95.0,
            "sample_values": ["test1@test.com", "test2@test.com"],
            "min_value": "test1@test.com",
            "max_value": "test9@test.com"
        }
    ],
    "structure": {
        "nested_fields": [],
        "array_fields": [],
        "flattened_paths": ["user_id", "user_email"],
        "max_depth": 1
    },
    "connector_metadata": {
        "bucket": "landing-bucket",
        "object_name": "raw_users_data.json"
    },
    "sample_records": []
}

def test_generate_embedding_optimized_text():
    text = generate_embedding_optimized_text(SAMPLE_METADATA)
    assert "Source Dataset Asset: Raw Users Data" in text
    assert "Structure Schema Fields:" in text
    assert "Under General Schema Columns:" in text
    assert "Column Name: User Id, Data Type: INT (unique identifier) (present in 100% of records)" in text
    assert "Column Name: User Email, Data Type: STR" in text
    # Test fallback name
    meta_no_name = SAMPLE_METADATA.copy()
    meta_no_name["connector_metadata"] = {}
    text_fallback = generate_embedding_optimized_text(meta_no_name)
    assert "Source Dataset Asset: Unknown Dataset" in text_fallback


def test_generate_llm_optimized_json():
    json_data = generate_llm_optimized_json(SAMPLE_METADATA)
    assert "connector_metadata" not in json_data
    assert "sample_records" not in json_data
    assert json_data["statistics"]["row_count"] == 100
    assert json_data["structure"]["max_depth"] == 1
    
    cols = json_data["columns"]
    assert len(cols) == 2
    assert cols[0]["name"] == "user_id"
    assert cols[0]["is_unique"] is True
    assert "null_count" in cols[0]
    
    assert cols[1]["name"] == "user_email"
    assert cols[1]["min_value"] == "test1@test.com"


def test_generate_target_llm_optimized_json():
    from app.services.metadata_service import generate_target_llm_optimized_json
    
    mock_target = MagicMock()
    mock_target.target_id = uuid.uuid4()
    mock_target.target_name = "target_users"
    mock_target.target_type = "POSTGRESQL"
    mock_target.business_domain = "Customer"
    mock_target.description = "User records"
    mock_target.schema_definition = {
        "fields": [
            {"name": "id", "type": "INTEGER", "primary_key": True, "nullable": False, "is_unique": True}
        ]
    }
    
    res = generate_target_llm_optimized_json(mock_target)
    assert res["target_name"] == "target_users"
    assert res["fields"][0]["primary_key"] is True
    assert res["fields"][0]["type"] == "INTEGER"


def test_save_metadata():
    mock_db = MagicMock()
    # Mock database query to return None so that a new profile is created and added
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    job_id = uuid.uuid4()
    artifact_id = uuid.uuid4()
    
    save_metadata(job_id, artifact_id, SAMPLE_METADATA, mock_db)
    
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


def test_sync_metadata_vector_processor():
    import asyncio
    
    async def run_test():
        mock_db = MagicMock()
        job_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        profile_id = str(uuid.uuid4())
        
        profile = MetadataProfile(
            metadata_profile_id=uuid.UUID(profile_id),
            job_id=uuid.UUID(job_id),
            artifact_id=uuid.UUID(artifact_id),
            metadata_json=SAMPLE_METADATA,
            embedding_optimized_text=None,
            source_embedding=None
        )
        
        mock_db.get.return_value = profile
        mock_vector = [0.123] * 768
        
        with patch("workers.vectorizers.metadata_vectorizer.processor.get_vector_embedding", new_callable=AsyncMock) as mock_embed, \
             patch("workers.vectorizers.metadata_vectorizer.processor.publish_metadata_vectorized") as mock_publish, \
             patch("workers.vectorizers.metadata_vectorizer.processor.start_stage") as mock_start_stage, \
             patch("workers.vectorizers.metadata_vectorizer.processor.complete_stage") as mock_complete_stage:
             
            mock_embed.return_value = mock_vector
            mock_stage = MagicMock()
            mock_stage.stage_history_id = uuid.uuid4()
            mock_start_stage.return_value = mock_stage
            
            await sync_metadata_vector(job_id, artifact_id, profile_id, mock_db)
            
            assert profile.embedding_optimized_text is not None
            assert profile.source_embedding == mock_vector
            mock_db.commit.assert_called_once()
            
            mock_start_stage.assert_called_once_with(uuid.UUID(job_id), "Metadata Vectorization", mock_db)
            mock_complete_stage.assert_called_once_with(mock_stage.stage_history_id, mock_db)
            
            mock_publish.assert_called_once_with(
                job_id=job_id,
                artifact_id=artifact_id,
                metadata_profile_id=profile_id
            )
            
    asyncio.run(run_test())
