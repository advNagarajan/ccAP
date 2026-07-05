import json
import uuid
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from uuid import UUID

from app.models.db.target_catalog import TargetCatalog
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.job import Job
from app.models.db.source import Source
from app.models.db.processing_configuration import ProcessingConfiguration
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_recommendation import SchemaRecommendation
from app.models.db.data_quality_report import DataQualityReport
from app.models.db.data_quality_job import DataQualityJob
from app.models.db.landing_inference import LandingInference

# Import components to test
from app.services.agents.tools import (
    get_validation_report,
    get_drift_report,
    get_source_metadata,
    get_data_quality_report,
    get_historical_recommendations,
    get_recommendation_feedback,
)
from app.services.agents.recommendation_agent import run_recommendation_agent
from workers.recommendation.processor import process_schema_recommendation


def test_tool_get_validation_report():
    db = MagicMock()
    val_id = uuid.uuid4()
    val = SchemaValidation(
        validation_id=val_id,
        validation_status="DRIFTED",
        coverage_percentage=90.0,
        target_match_percentage=85.0,
        mapped_column_count=9,
        source_column_count=10,
        target_column_count=11,
        report_json={"mismatches": []}
    )
    db.get.return_value = val

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = asyncio.run(get_validation_report(str(val_id), tool_context))
    res = json.loads(res_str)

    assert res["validation_status"] == "DRIFTED"
    assert res["coverage_percentage"] == 90.0
    assert res["mapped_column_count"] == 9


def test_tool_get_drift_report():
    db = MagicMock()
    drift_id = uuid.uuid4()
    drift = SchemaDrift(
        drift_id=drift_id,
        drift_status="DRIFTED",
        drift_score=0.15,
        drift_summary={"new_columns": ["email"]}
    )
    db.get.return_value = drift

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = asyncio.run(get_drift_report(str(drift_id), tool_context))
    res = json.loads(res_str)

    assert res["drift_status"] == "DRIFTED"
    assert res["drift_score"] == 0.15
    assert "email" in res["drift_summary"]["new_columns"]


def test_tool_get_source_metadata():
    db = MagicMock()
    job_id = uuid.uuid4()
    profile = MetadataProfile(
        metadata_profile_id=uuid.uuid4(),
        job_id=job_id,
        metadata_json={
            "statistics": {"row_count": 100, "column_count": 2},
            "columns": [{"name": "id", "observed_types": ["int"]}],
            "structure": {"max_depth": 1}
        }
    )
    
    mock_scalars = MagicMock()
    mock_scalars.scalar_one_or_none.return_value = profile
    db.execute.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {"db": db, "job_id": str(job_id)}
    res_str = asyncio.run(get_source_metadata(tool_context))
    res = json.loads(res_str)

    assert res["statistics"]["row_count"] == 100
    assert res["columns"][0]["name"] == "id"


def test_tool_get_data_quality_report():
    db = MagicMock()
    job_id = uuid.uuid4()
    
    report = DataQualityReport(
        report_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        artifact_id=uuid.uuid4(),
        status="PASSED",
        rules_executed=5,
        rules_failed=0,
        report_json={"rules": [{"name": "null_check", "status": "PASSED"}]}
    )
    
    mock_scalars = MagicMock()
    mock_scalars.scalars.return_value.first.return_value = report
    db.execute.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {"db": db, "job_id": str(job_id)}
    res_str = asyncio.run(get_data_quality_report(tool_context))
    res = json.loads(res_str)

    assert res["status"] == "PASSED"
    assert res["rules_executed"] == 5
    assert len(res["rules"]) == 1


def test_tool_get_historical_recommendations():
    db = MagicMock()
    target_id = uuid.uuid4()
    rec = SchemaRecommendation(
        recommendation_id=uuid.uuid4(),
        target_id=target_id,
        recommendation_status="COMPLETED",
        recommendations_list=[{"column_name": "email"}],
        explanation="Remediation plan done"
    )
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [rec]
    db.scalars.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = asyncio.run(get_historical_recommendations(str(target_id), tool_context))
    res = json.loads(res_str)

    assert len(res) == 1
    assert res[0]["explanation"] == "Remediation plan done"


def test_tool_get_recommendation_feedback():
    db = MagicMock()
    feedback = LlmFeedbackLoop(
        feedback_id=uuid.uuid4(),
        stage="recommendation",
        engineer_notes="Always recommend default for phone",
        user_action="Accept",
        response_in_question="Modify type"
    )
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [feedback]
    db.scalars.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = asyncio.run(get_recommendation_feedback(tool_context))
    res = json.loads(res_str)

    assert len(res) == 1
    assert res[0]["engineer_notes"] == "Always recommend default for phone"


def test_run_recommendation_agent_wrapper():
    async def run_async_test():
        db = MagicMock()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        
        mock_part = MagicMock()
        agent_output = {
            "recommendations": [
                {
                    "sequence_order": 1,
                    "action_type": "ADD_COLUMN",
                    "target": "target",
                    "column_name": "email",
                    "new_column_name": None,
                    "data_type": "VARCHAR",
                    "priority": "HIGH",
                    "reason": "missing",
                    "suggested_action": "ALTER TABLE orders ADD COLUMN email VARCHAR;",
                    "confidence_score": 0.95
                }
            ],
            "explanation": " remediation explanation",
            "impact_assessment": {"breaking_changes": []},
            "transformation_plan": {"target_type": "POSTGRESQL"},
            "data_quality_flags": [],
            "risk_level": "LOW",
            "estimated_effort": "LOW"
        }
        mock_part.text = json.dumps(agent_output)
        mock_event.content.parts = [mock_part]

        async def mock_run_async(*args, **kwargs):
            yield mock_event

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = mock_run_async

        with patch("app.services.agents.recommendation_agent.Runner", return_value=mock_runner_instance):
            res = await run_recommendation_agent(
                job_id=str(uuid.uuid4()),
                target_id=str(uuid.uuid4()),
                validation_id=str(uuid.uuid4()),
                drift_id=str(uuid.uuid4()),
                partitioning_recommendation=None,
                db=db
            )
            assert len(res["recommendations"]) == 1
            assert res["explanation"] == " remediation explanation"
            assert res["risk_level"] == "LOW"

    asyncio.run(run_async_test())


def test_recommendation_processor_routing():
    async def run_async_test():
        db = MagicMock()
        job_uuid = uuid.uuid4()
        artifact_uuid = uuid.uuid4()
        drift_uuid = uuid.uuid4()
        validation_uuid = uuid.uuid4()
        source_uuid = uuid.uuid4()
        config_uuid = uuid.uuid4()
        target_uuid = uuid.uuid4()

        # Stub models
        drift = SchemaDrift(
            drift_id=drift_uuid,
            job_id=job_uuid,
            artifact_id=artifact_uuid,
            validation_id=validation_uuid,
            target_id=target_uuid,
            drift_status="DRIFTED",
            drift_score=0.2,
            drift_summary={"new_columns": []}
        )
        val = SchemaValidation(
            validation_id=validation_uuid,
            job_id=job_uuid,
            artifact_id=artifact_uuid,
            inference_id=uuid.uuid4(),
            target_id=target_uuid,
            validation_status="DRIFTED",
            coverage_percentage=100.0,
            target_match_percentage=100.0,
            mapped_column_count=5,
            source_column_count=5,
            target_column_count=5,
            report_json={"invalid_mappings": []}
        )
        job = Job(
            job_id=job_uuid,
            source_id=source_uuid
        )
        source = Source(
            source_id=source_uuid,
            config_id=config_uuid
        )
        config = ProcessingConfiguration(
            config_id=config_uuid,
            config_content={"enable_agentic_pipeline": True}
        )
        target = TargetCatalog(
            target_id=target_uuid,
            target_name="test_target",
            target_type="POSTGRESQL"
        )
        inference = LandingInference(
            inference_id=val.inference_id,
            job_id=job_uuid,
            artifact_id=artifact_uuid,
            metadata_profile_id=uuid.uuid4(),
            target_id=target_uuid,
            confidence_score=0.9,
            reasoning="Selection reasoning",
            partitioning_recommendation="partition by order_date"
        )

        def db_get(model, ident):
            return {
                SchemaDrift: drift,
                SchemaValidation: val,
                Job: job,
                Source: source,
                ProcessingConfiguration: config,
                TargetCatalog: target,
                LandingInference: inference
            }.get(model)
            
        db.get = db_get

        # Mock stage & Pub/Sub
        mock_stage = MagicMock()
        mock_stage.stage_history_id = uuid.uuid4()
        
        db.execute.return_value.scalar_one_or_none.return_value = None

        mock_agent_output = {
            "recommendations": [
                {
                    "sequence_order": 1,
                    "action_type": "ADD_COLUMN",
                    "target": "target",
                    "column_name": "email",
                    "new_column_name": None,
                    "data_type": "VARCHAR",
                    "priority": "HIGH",
                    "reason": "missing",
                    "suggested_action": "ALTER TABLE orders ADD COLUMN email VARCHAR;",
                    "confidence_score": 0.95
                }
            ],
            "explanation": "Remediation plan proposed via agent",
            "impact_assessment": {"breaking_changes": []},
            "transformation_plan": {"target_type": "POSTGRESQL"},
            "data_quality_flags": [],
            "risk_level": "LOW",
            "estimated_effort": "LOW"
        }

        with patch("workers.recommendation.processor.start_stage", return_value=mock_stage), \
             patch("workers.recommendation.processor.complete_stage") as mock_complete, \
             patch("workers.recommendation.processor.update_job_status_from_artifacts"), \
             patch("workers.recommendation.processor.publish_job_completed"), \
             patch("app.services.agents.recommendation_agent.run_recommendation_agent", new_callable=AsyncMock, return_value=mock_agent_output) as mock_agent:

            await process_schema_recommendation(
                job_id=str(job_uuid),
                artifact_id=str(artifact_uuid),
                drift_id=str(drift_uuid),
                db=db
            )

            # Verify ADK agent is called
            mock_agent.assert_called_once()
            
            # Verify complete_stage is called with execution_path details
            mock_complete.assert_called_once()
            complete_details = mock_complete.call_args[1]["details"]
            assert complete_details["execution_path"] == "AGENTIC"

    asyncio.run(run_async_test())
