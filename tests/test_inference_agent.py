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

# Import components to test
from app.services.agents.tools import (
    search_candidate_targets,
    get_target_schema_details,
    check_type_compatibility,
    get_feedback_guidelines,
)
from app.services.agents.inference_agent import run_inference_agent
from workers.inference.processor import infer_target_landing_zone


def test_tool_check_type_compatibility():
    # Compatible
    res = json.loads(check_type_compatibility("int", "INTEGER"))
    assert res["status"] == "COMPATIBLE"

    # Warning
    res = json.loads(check_type_compatibility("float", "INTEGER"))
    assert res["status"] == "WARNING"

    # Incompatible
    res = json.loads(check_type_compatibility("dict", "INTEGER"))
    assert res["status"] == "INCOMPATIBLE"

    # Deferred (e.g. unknown or NoSQL/file targets)
    res = json.loads(check_type_compatibility("dict", "UNKNOWN_TYPE"))
    assert res["status"] == "DEFERRED"


def test_tool_get_feedback_guidelines():
    db = MagicMock()
    feedback1 = LlmFeedbackLoop(
        feedback_id=uuid.uuid4(),
        stage="inference",
        engineer_notes="Guideline 1",
        user_action="Accept"
    )
    feedback2 = LlmFeedbackLoop(
        feedback_id=uuid.uuid4(),
        stage="recomm_inference",
        engineer_notes="Guideline 2",
        user_action="Reject"
    )
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [feedback1, feedback2]
    db.scalars.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = get_feedback_guidelines(tool_context)
    res = json.loads(res_str)

    assert len(res) == 2
    assert res[0]["engineer_notes"] == "Guideline 1"
    assert res[1]["engineer_notes"] == "Guideline 2"


def test_tool_get_target_schema_details():
    db = MagicMock()
    target_id = uuid.uuid4()
    target = TargetCatalog(
        target_id=target_id,
        target_name="test_target",
        target_type="POSTGRESQL",
        business_domain="finance",
        description="test description",
        schema_definition={
            "fields": [
                {"name": "id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "VARCHAR", "nullable": True}
            ]
        }
    )
    db.get.return_value = target

    tool_context = MagicMock()
    tool_context.state = {"db": db}
    res_str = get_target_schema_details(str(target_id), tool_context)
    res = json.loads(res_str)

    assert res["target_name"] == "test_target"
    assert len(res["fields"]) == 2
    assert res["fields"][0]["name"] == "id"
    assert res["fields"][0]["primary_key"] is True


def test_tool_search_candidate_targets_predefined():
    db = MagicMock()
    target_id = uuid.uuid4()
    target = TargetCatalog(
        target_id=target_id,
        target_name="test_predefined",
        target_type="POSTGRESQL",
        business_domain="finance",
        description="test",
        schema_definition={"fields": [{"name": "id", "type": "INTEGER"}]}
    )
    
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [target]
    db.scalars.return_value = mock_scalars

    tool_context = MagicMock()
    tool_context.state = {
        "db": db,
        "predefined_target_ids": [str(target_id)]
    }
    res_str = search_candidate_targets("summary text", tool_context)
    res = json.loads(res_str)

    assert len(res) == 1
    assert res[0]["target_id"] == str(target_id)
    assert res[0]["similarity_score"] == 1.0


def test_tool_search_candidate_targets_semantic():
    db = MagicMock()
    target = TargetCatalog(
        target_id=uuid.uuid4(),
        target_name="test_semantic",
        target_type="POSTGRESQL",
        business_domain="finance",
        description="test",
        schema_definition={"fields": [{"name": "id", "type": "INTEGER"}]}
    )
    
    db.execute.return_value.all.return_value = [(target, 0.85)]

    tool_context = MagicMock()
    tool_context.state = {
        "db": db,
        "predefined_target_ids": [],
        "source_embedding": [0.1, 0.2, 0.3]
    }
    res_str = search_candidate_targets("summary text", tool_context)
    res = json.loads(res_str)

    assert len(res) == 1
    assert res[0]["similarity_score"] == 0.85
    assert res[0]["target_name"] == "test_semantic"


def test_run_inference_agent_wrapper():
    async def run_async_test():
        db = MagicMock()
        mock_event = MagicMock()
        mock_event.is_final_response.return_value = True
        
        mock_part = MagicMock()
        agent_output = {
            "selected_target_id": str(uuid.uuid4()),
            "confidence_score": 0.95,
            "reasoning": "Mapped correctly",
            "column_mapping": {"src": "tgt"},
            "unmapped_source_columns": [],
            "missing_target_columns": [],
            "partitioning_recommendation": "partition by date",
            "naming_convention_suggestions": {}
        }
        mock_part.text = json.dumps(agent_output)
        mock_event.content.parts = [mock_part]

        async def mock_run_async(*args, **kwargs):
            yield mock_event

        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = mock_run_async

        with patch("app.services.agents.inference_agent.Runner", return_value=mock_runner_instance):
            res = await run_inference_agent(
                job_id=str(uuid.uuid4()),
                source_json={"columns": []},
                source_embedding=[0.1, 0.2],
                predefined_target_ids=[],
                db=db
            )
            assert res["selected_target_id"] == agent_output["selected_target_id"]
            assert res["confidence_score"] == 0.95

    asyncio.run(run_async_test())


def test_infer_target_landing_zone_routing():
    async def run_async_test():
        db = MagicMock()
        job_uuid = uuid.uuid4()
        profile_uuid = uuid.uuid4()
        source_uuid = uuid.uuid4()
        config_uuid = uuid.uuid4()
        target_uuid = uuid.uuid4()

        # Stub models
        profile = MetadataProfile(
            metadata_profile_id=profile_uuid,
            job_id=job_uuid,
            source_embedding=[0.1, 0.2],
            metadata_json={"columns": []}
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
            config_content={"enable_agentic_pipeline": True, "predefined_target_ids": []}
        )
        target = TargetCatalog(
            target_id=target_uuid,
            target_name="test_target",
            target_type="POSTGRESQL",
            schema_definition={"fields": []}
        )

        def db_get(model, ident):
            return {
                MetadataProfile: profile,
                Job: job,
                Source: source,
                ProcessingConfiguration: config,
                TargetCatalog: target
            }.get(model)
            
        db.get = db_get

        # Mock stage & Pub/Sub
        mock_stage = MagicMock()
        mock_stage.stage_history_id = uuid.uuid4()
        
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        db.scalars.return_value = mock_scalars
        
        db.execute.return_value.scalar_one_or_none.return_value = None

        mock_agent_output = {
            "selected_target_id": str(target_uuid),
            "confidence_score": 0.95,
            "reasoning": "Mapped correctly via agent",
            "column_mapping": {"src": "tgt"},
            "unmapped_source_columns": [],
            "missing_target_columns": [],
            "partitioning_recommendation": "partition by date",
            "naming_convention_suggestions": {}
        }

        with patch("workers.inference.processor.start_stage", return_value=mock_stage), \
             patch("workers.inference.processor.complete_stage"), \
             patch("workers.inference.processor.publish_target_inferred"), \
             patch("app.services.agents.inference_agent.run_inference_agent", new_callable=AsyncMock, return_value=mock_agent_output) as mock_agent:

            await infer_target_landing_zone(
                job_id=str(job_uuid),
                artifact_id=str(uuid.uuid4()),
                metadata_profile_id=str(profile_uuid),
                db=db
            )

            mock_agent.assert_called_once()

    asyncio.run(run_async_test())
