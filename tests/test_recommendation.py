import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.models.db.job import Job
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_validation import SchemaValidation
from app.models.db.landing_inference import LandingInference
from app.models.db.target_catalog import TargetCatalog
from app.models.db.schema_recommendation import SchemaRecommendation
from app.models.domain.recommendation_schema import SchemaRecommendationOutput, RecommendationOp
from app.services.recommendation_service import extract_deterministic_findings, generate_schema_recommendations
from workers.recommendation.processor import process_schema_recommendation


def test_extract_deterministic_findings():
    # 1. Input validation/drift data
    validation_report = {
        "missing_target_columns": ["col_a", "col_b"],
        "additional_source_columns": ["col_c"],
        "datatype_issues": [
            {
                "source_column": "col_d",
                "target_column": "col_d",
                "source_type": "str",
                "target_type": "INTEGER",
                "reason": "Type conversion incompatibility"
            }
        ]
    }
    drift_report = {
        "drift_summary": {
            "renamed_columns": [
                {
                    "source_column": "col_e_src",
                    "target_column": "col_e"
                }
            ]
        }
    }

    # 2. Extract findings
    findings = extract_deterministic_findings(validation_report, drift_report)

    # 3. Assertions
    assert findings["missing_target_columns"] == ["col_a", "col_b"]
    assert findings["additional_source_columns"] == ["col_c"]
    assert len(findings["datatype_mismatches"]) == 1
    assert findings["datatype_mismatches"][0]["source_column"] == "col_d"
    assert len(findings["renamed_columns"]) == 1
    assert findings["renamed_columns"][0]["source_column"] == "col_e_src"


@pytest.mark.anyio
async def test_generate_schema_recommendations_relational():
    # Mock LLM provider
    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = """{
        "recommendations": [
            {
                "sequence_order": 1,
                "action_type": "ADD_COLUMN",
                "target": "target",
                "column_name": "col_c",
                "new_column_name": null,
                "data_type": "VARCHAR(255)",
                "priority": "HIGH",
                "reason": "Add valuable source column to target table",
                "suggested_action": "ALTER TABLE users ADD COLUMN col_c VARCHAR(255);",
                "confidence_score": 0.95
            }
        ],
        "explanation": "Added col_c to relational target."
    }"""

    target_catalog = TargetCatalog(
        target_name="users",
        target_type="POSTGRESQL",
        schema_definition={"fields": []}
    )

    with patch("app.services.recommendation_service.get_llm_provider", return_value=mock_llm):
        result = await generate_schema_recommendations(
            findings={"additional_source_columns": ["col_c"]},
            target_catalog=target_catalog,
            partitioning_rec="PARTITION BY RANGE(created_at)"
        )

        assert len(result.recommendations) == 1
        assert result.recommendations[0].action_type == "ADD_COLUMN"
        assert result.recommendations[0].suggested_action == "ALTER TABLE users ADD COLUMN col_c VARCHAR(255);"
        assert result.recommendations[0].confidence_score == 0.95
        assert "users" in mock_llm.generate_response.call_args[1]["prompt"]


@pytest.mark.anyio
async def test_process_recommendation_flow():
    db = MagicMock()
    job_id = str(uuid.uuid4())
    artifact_id = str(uuid.uuid4())
    validation_id = str(uuid.uuid4())
    drift_id = str(uuid.uuid4())
    target_id = str(uuid.uuid4())
    inference_id = str(uuid.uuid4())

    drift_rec = SchemaDrift(
        drift_id=uuid.UUID(drift_id),
        job_id=uuid.UUID(job_id),
        validation_id=uuid.UUID(validation_id),
        target_id=uuid.UUID(target_id),
        drift_status="DRIFTED",
        drift_score=25.0,
        drift_summary={"renamed_columns": []}
    )

    val_rec = SchemaValidation(
        validation_id=uuid.UUID(validation_id),
        job_id=uuid.UUID(job_id),
        inference_id=uuid.UUID(inference_id),
        target_id=uuid.UUID(target_id),
        validation_status="WARNING",
        coverage_percentage=90.0,
        target_match_percentage=90.0,
        mapped_column_count=2,
        source_column_count=3,
        target_column_count=3,
        report_json={"missing_target_columns": ["col_a"]}
    )

    target_cat = TargetCatalog(
        target_id=uuid.UUID(target_id),
        target_name="users",
        target_type="POSTGRESQL",
        connection_details={},
        schema_definition={}
    )

    inference = LandingInference(
        inference_id=uuid.UUID(inference_id),
        job_id=uuid.UUID(job_id),
        artifact_id=uuid.UUID(artifact_id),
        metadata_profile_id=uuid.uuid4(),
        target_id=uuid.UUID(target_id),
        confidence_score=0.9,
        partitioning_recommendation="PARTITION BY created_at"
    )

    job = Job(
        job_id=uuid.UUID(job_id),
        source_id=uuid.uuid4(),
        status="RUNNING"
    )

    db.get = lambda model, ident: {
        SchemaDrift: drift_rec,
        SchemaValidation: val_rec,
        TargetCatalog: target_cat,
        LandingInference: inference,
        Job: job
    }.get(model)

    db.execute.return_value.scalar_one_or_none.return_value = None

    mock_llm_out = SchemaRecommendationOutput(
        recommendations=[
            RecommendationOp(
                sequence_order=1,
                action_type="ADD_NULLABLE_HANDLING",
                target="source",
                column_name="col_a",
                priority="MEDIUM",
                reason="Add nullable handling to source for col_a",
                suggested_action="Configure source mapping default to NULL for col_a",
                confidence_score=0.9
            )
        ],
        explanation="Source transformation preferred."
    )

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.recommendation.processor.start_stage", return_value=mock_stage) as mock_start, \
         patch("workers.recommendation.processor.complete_stage") as mock_complete, \
         patch("workers.recommendation.processor.generate_schema_recommendations", return_value=mock_llm_out), \
         patch("workers.recommendation.processor.publish_job_completed") as mock_publish_completed:

        rec_record = await process_schema_recommendation(job_id, artifact_id, drift_id, db)

        assert rec_record.recommendation_status == "COMPLETED"
        assert rec_record.partitioning_recommendation == "PARTITION BY created_at"
        assert len(rec_record.recommendations_list) == 1
        assert rec_record.recommendations_list[0]["action_type"] == "ADD_NULLABLE_HANDLING"

        mock_complete.assert_called_once()
        mock_publish_completed.assert_called_once_with(
            job_id=job_id,
            source_id=str(job.source_id),
            recommendations_count=1,
            target_name="users"
        )
