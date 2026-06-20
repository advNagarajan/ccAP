import uuid
import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.target_catalog import TargetCatalog
from app.models.db.llm_feedback_loop import LlmFeedbackLoop
from app.models.db.user import User
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_validation import SchemaValidation
from app.models.db.landing_inference import LandingInference
from app.models.db.job import Job
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.metadata_profile import MetadataProfile
from app.models.domain.recommendation_schema import SchemaRecommendationOutput, RecommendationOp

from app.services.recommendation_service import generate_schema_recommendations
from workers.inference.processor import infer_target_landing_zone
from workers.recommendation.processor import process_schema_recommendation

# Mock DB Session
mock_db = MagicMock()
mock_users_db = {}
mock_feedback_db = {}

def mock_add(instance):
    if isinstance(instance, User):
        if not getattr(instance, "user_id", None):
            instance.user_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        mock_users_db[instance.user_id] = instance
    elif isinstance(instance, LlmFeedbackLoop):
        if not getattr(instance, "feedback_id", None):
            instance.feedback_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        mock_feedback_db[instance.feedback_id] = instance

mock_db.add = mock_add

def mock_execute(statement):
    result_mock = MagicMock()
    stmt_str = str(statement).lower()
    
    # User duplicate check by email
    if "users.email" in stmt_str:
        email = None
        # Extract email from the compiled statement parameters or simulate not found
        # For our test, if mock_users_db is not empty and we are looking up, return one
        if mock_users_db:
            result_mock.scalar_one_or_none.return_value = list(mock_users_db.values())[0]
        else:
            result_mock.scalar_one_or_none.return_value = None
    # User lookup
    elif "users" in stmt_str:
        result_mock.scalar_one_or_none.return_value = list(mock_users_db.values())[0] if mock_users_db else None
    return result_mock

mock_db.execute = mock_execute

# Override FastAPI get_db dependency
def override_get_db():
    try:
        yield mock_db
    finally:
        pass

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_auth_and_stage_feedback():
    print("\n" + "=" * 60)
    print("TEST 1 - USER REGISTRATION & LOGIN")
    print("=" * 60)

    # 1. Register User
    register_response = client.post(
        "/auth/register",
        json={
            "email": "engineer@sutherland.com",
            "password": "SecurePassword123!"
        }
    )
    assert register_response.status_code == 201
    user_data = register_response.json()
    user_id = user_data["user_id"]
    assert user_data["email"] == "engineer@sutherland.com"

    # 2. Login User
    login_response = client.post(
        "/auth/login",
        json={
            "email": "engineer@sutherland.com",
            "password": "SecurePassword123!"
        }
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "token-" in token_data["access_token"]
    assert token_data["user"]["user_id"] == user_id
    print("PASS: Registration & Login completed successfully.")

    print("\n" + "=" * 60)
    print("TEST 2 - SUBMIT STAGE-SPECIFIC FEEDBACK")
    print("=" * 60)

    job_id = str(uuid.uuid4())
    feedback_response = client.post(
        "/feedback",
        json={
            "job_id": job_id,
            "stage": "inference",
            "response_in_question": "Selected target was raw_events",
            "engineer_notes": "Do not select raw_events for transaction data. Route to ledger.",
            "user_id": user_id
        }
    )
    assert feedback_response.status_code == 201
    fb_data = feedback_response.json()
    assert fb_data["stage"] == "inference"
    assert fb_data["user_id"] == user_id
    assert fb_data["target_id"] is None
    print("PASS: Stage-specific feedback successfully saved.")


@pytest.mark.anyio
async def test_inference_prompt_injection():
    print("\n" + "=" * 60)
    print("TEST 3 - INFERENCE PROMPT INJECTION")
    print("=" * 60)

    # Set up mocked DB data for inference run
    job_uuid = uuid.uuid4()
    profile_uuid = uuid.uuid4()
    artifact_uuid = uuid.uuid4()

    mock_job = Job(job_id=job_uuid, source_id=uuid.uuid4(), status="RUNNING")
    
    # Add some mock feedback loop records for the job
    mock_feedback = LlmFeedbackLoop(
        job_id=job_uuid,
        stage="inference",
        engineer_notes="Prefer finance ledger for invoice schema"
    )

    db_mock = MagicMock()
    db_mock.get.side_effect = lambda model, ident: {
        Job: mock_job,
        MetadataProfile: MagicMock(
            metadata_profile_id=profile_uuid,
            artifact_id=artifact_uuid,
            metadata_json={"fields": [{"name": "id", "type": "INTEGER"}]},
            source_embedding=[0.1]*768
        ),
        TargetCatalog: TargetCatalog(
            target_id=uuid.uuid4(),
            target_name="finance_ledger",
            target_type="POSTGRESQL",
            schema_definition={"fields": []}
        )
    }.get(model)

    db_mock.scalars.return_value.all.return_value = [mock_feedback]
    db_mock.execute.return_value.all.return_value = [
        (TargetCatalog(target_id=uuid.uuid4(), target_name="finance_ledger", schema_definition={"fields": []}), 0.95)
    ]
    db_mock.execute.return_value.scalar_one_or_none.return_value = None

    mock_llm = AsyncMock()
    mock_llm.generate_response.return_value = """{
        "selected_target_id": "8bf9e75e-8d66-4f87-a966-2244bbccddaa",
        "confidence_score": 0.99,
        "reasoning": "Matching based on target notes",
        "column_mapping": {},
        "unmapped_source_columns": [],
        "missing_target_columns": [],
        "partitioning_recommendation": null,
        "naming_convention_suggestions": {}
    }"""

    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()

    with patch("workers.inference.processor.get_llm_provider", return_value=mock_llm), \
         patch("workers.inference.processor.start_stage", return_value=mock_stage), \
         patch("workers.inference.processor.complete_stage"), \
         patch("workers.inference.processor.publish_target_inferred"):
        
        await infer_target_landing_zone(
            job_id=str(job_uuid),
            artifact_id=str(artifact_uuid),
            metadata_profile_id=str(profile_uuid),
            db=db_mock
        )

        # Retrieve prompt passed to generate_response
        call_args = mock_llm.generate_response.call_args
        prompt_text = call_args[1]["prompt"]
        
        assert "Human Engineering Feedback Guidelines:" in prompt_text
        assert "Prefer finance ledger for invoice schema" in prompt_text
        print("PASS: Inference prompt correctly injected with stage feedback.")


if __name__ == "__main__":
    test_auth_and_stage_feedback()
    import asyncio
    asyncio.run(test_inference_prompt_injection())
