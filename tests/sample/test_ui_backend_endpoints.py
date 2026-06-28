import uuid
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.user import User
from app.models.db.job import Job
from app.models.db.audit_log import AuditLog
from app.models.db.job_stage_history import JobStageHistory
from app.models.db.landing_inference import LandingInference
from app.models.db.schema_validation import SchemaValidation
from app.models.db.schema_drift import SchemaDrift
from app.models.db.schema_recommendation import SchemaRecommendation
from app.models.db.metadata_profile import MetadataProfile
from app.models.db.target_catalog import TargetCatalog

# Mock DB Session
mock_db = MagicMock()
mock_users_db = {}
mock_jobs_db = {}
mock_audit_db = {}

def mock_add(instance):
    if isinstance(instance, User):
        if not getattr(instance, "user_id", None):
            instance.user_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        mock_users_db[instance.user_id] = instance
    elif isinstance(instance, Job):
        if not getattr(instance, "job_id", None):
            instance.job_id = uuid.uuid4()
        if getattr(instance, "retry_count", None) is None:
            instance.retry_count = 0
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        if not getattr(instance, "updated_at", None):
            instance.updated_at = datetime.utcnow()
        mock_jobs_db[instance.job_id] = instance
    elif isinstance(instance, AuditLog):
        if not getattr(instance, "log_id", None):
            instance.log_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        mock_audit_db[instance.log_id] = instance

mock_db.add = mock_add

def mock_delete(instance):
    if isinstance(instance, User):
        mock_users_db.pop(instance.user_id, None)
    elif isinstance(instance, Job):
        mock_jobs_db.pop(instance.job_id, None)

mock_db.delete = mock_delete

def mock_get(model_class, ident):
    if model_class == User:
        if isinstance(ident, str):
            ident = uuid.UUID(ident)
        return mock_users_db.get(ident)
    elif model_class == Job:
        if isinstance(ident, str):
            ident = uuid.UUID(ident)
        return mock_jobs_db.get(ident)
    return None

mock_db.get = mock_get

def mock_execute(statement):
    result_mock = MagicMock()
    stmt_str = str(statement).lower()
    
    if "where" in stmt_str and "email" in stmt_str:
        # Simple search by email helper for register/login tests
        for u in mock_users_db.values():
            if f"'{u.email}'" in stmt_str or f"email = '{u.email}'" in stmt_str or f"users.email = '{u.email}'" in stmt_str:
                result_mock.scalar_one_or_none.return_value = u
                return result_mock
        result_mock.scalar_one_or_none.return_value = None
    elif "users" in stmt_str:
        result_mock.scalars.return_value.all.return_value = list(mock_users_db.values())
    elif "audit_logs" in stmt_str:
        result_mock.scalars.return_value.all.return_value = list(mock_audit_db.values())
    elif "job_stage_history" in stmt_str:
        result_mock.scalars.return_value.all.return_value = []
    elif "landing_inferences" in stmt_str:
        result_mock.scalar_one_or_none.return_value = None
    elif "schema_validations" in stmt_str:
        result_mock.scalar_one_or_none.return_value = None
    elif "schema_drifts" in stmt_str:
        result_mock.scalar_one_or_none.return_value = None
    elif "schema_recommendations" in stmt_str:
        result_mock.scalar_one_or_none.return_value = None
    elif "metadata_profiles" in stmt_str:
        result_mock.scalar_one_or_none.return_value = None
    elif "data_quality_reports" in stmt_str or "data_quality_jobs" in stmt_str:
        result_mock.scalars.return_value.first.return_value = None
        result_mock.scalar_one_or_none.return_value = None
    
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


def test_user_roles_and_permissions():
    mock_users_db.clear()
    
    # 1. Create a regular user, an admin user, and an owner user
    owner = User(
        email="owner@sutherland.com",
        hashed_password="hashed_password_1",
        role="OWNER"
    )
    mock_add(owner)
    
    admin = User(
        email="admin@sutherland.com",
        hashed_password="hashed_password_2",
        role="ADMIN"
    )
    mock_add(admin)
    
    regular_user = User(
        email="user@sutherland.com",
        hashed_password="hashed_password_3",
        role="USER"
    )
    mock_add(regular_user)
    
    # Create tokens for test headers
    owner_token = f"Bearer token-{owner.user_id}"
    admin_token = f"Bearer token-{admin.user_id}"
    user_token = f"Bearer token-{regular_user.user_id}"

    # 2. Get Users - user_token (Forbidden 403)
    response = client.get("/auth/users", headers={"Authorization": user_token})
    assert response.status_code == 403

    # 3. Get Users - admin_token (Success 200)
    response = client.get("/auth/users", headers={"Authorization": admin_token})
    assert response.status_code == 200
    users_list = response.json()
    assert len(users_list) == 3

    # 4. Patch user role - adminpromoting regular user to ADMIN
    response = client.patch(
        f"/auth/users/{regular_user.user_id}/role",
        json={"role": "ADMIN"},
        headers={"Authorization": admin_token}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"
    assert regular_user.role == "ADMIN"

    # 5. Patch OWNER role - Admin trying to patch Owner role should fail with 403
    response = client.patch(
        f"/auth/users/{owner.user_id}/role",
        json={"role": "USER"},
        headers={"Authorization": admin_token}
    )
    assert response.status_code == 403

    # 6. Delete OWNER - Admin trying to delete OWNER should fail with 403
    response = client.delete(
        f"/auth/users/{owner.user_id}",
        headers={"Authorization": admin_token}
    )
    assert response.status_code == 403

    # 7. Delete Admin - Admin deleting promoted user (which is now Admin) should succeed
    response = client.delete(
        f"/auth/users/{regular_user.user_id}",
        headers={"Authorization": admin_token}
    )
    assert response.status_code == 204
    assert regular_user.user_id not in mock_users_db


def test_job_details_unified():
    # Setup mock job in db
    mock_jobs_db.clear()
    job_uuid = uuid.uuid4()
    job = Job(
        job_id=job_uuid,
        source_id=uuid.uuid4(),
        status="RUNNING",
        current_stage="Extraction"
    )
    mock_add(job)

    # Fetch details
    response = client.get(f"/jobs/{job_uuid}/details")
    assert response.status_code == 200
    details = response.json()
    assert details["job"]["job_id"] == str(job_uuid)
    assert details["job"]["status"] == "RUNNING"
    assert details["artifacts"] == []


def test_audit_logs():
    mock_audit_db.clear()
    mock_users_db.clear()
    
    admin = User(
        email="admin@sutherland.com",
        hashed_password="hashed_password",
        role="ADMIN"
    )
    mock_add(admin)
    admin_token = f"Bearer token-{admin.user_id}"

    # Log an manual audit event
    log = AuditLog(
        user_email="admin@sutherland.com",
        action="Trigger Ingestion",
        details={"source_id": str(uuid.uuid4())}
    )
    mock_add(log)

    # Fetch audit logs
    response = client.get("/audit-logs", headers={"Authorization": admin_token})
    assert response.status_code == 200
    logs = response.json()
    assert len(logs) == 1
    assert logs[0]["action"] == "Trigger Ingestion"
    assert logs[0]["user_email"] == "admin@sutherland.com"


def test_job_details_with_data_quality():
    # Clear mocks
    mock_jobs_db.clear()
    
    job_uuid = uuid.uuid4()
    artifact_uuid = uuid.uuid4()
    source_uuid = uuid.uuid4()
    
    # 1. Create a job
    job = Job(
        job_id=job_uuid,
        source_id=source_uuid,
        status="SUCCESS",
        current_stage="Dataset Published"
    )
    mock_add(job)
    
    # 2. Mock db execute to return inferences, validations, drift, targets, fallback, and data quality
    from app.models.db.landing_inference import LandingInference
    from app.models.db.artifact_record import ArtifactRecord
    from app.models.db.data_quality_report import DataQualityReport
    
    mock_inf = LandingInference(
        inference_id=uuid.uuid4(),
        job_id=job_uuid,
        artifact_id=artifact_uuid,
        confidence_score=0.95,
        column_mapping={"id": "id"},
        unmapped_source_columns=[],
        missing_target_columns=[],
        reasoning="Good match",
        requires_review=False
    )
    
    mock_art = ArtifactRecord(
        artifact_id=artifact_uuid,
        source_id=source_uuid,
        external_artifact_id="gcs://bucket/file.csv",
        artifact_name="file.csv",
        status="COMPLETED"
    )
    
    mock_dq_report = DataQualityReport(
        report_id=uuid.uuid4(),
        job_id=uuid.uuid4(),
        artifact_id=artifact_uuid,
        status="PASSED",
        rules_executed=5,
        rules_failed=0,
        report_json={"summary": "passed"},
        created_at=datetime.utcnow()
    )
    
    def custom_execute(statement):
        result_mock = MagicMock()
        stmt_str = str(statement).lower()
        
        if "landing_inferences" in stmt_str:
            result_mock.scalars.return_value.all.return_value = [mock_inf]
        elif "data_quality_reports" in stmt_str:
            result_mock.scalars.return_value.first.return_value = mock_dq_report
        elif "schema_validations" in stmt_str:
            result_mock.scalar_one_or_none.return_value = None
        elif "schema_drifts" in stmt_str:
            result_mock.scalar_one_or_none.return_value = None
        elif "schema_recommendations" in stmt_str:
            result_mock.scalar_one_or_none.return_value = None
        elif "schema_fallback_requests" in stmt_str:
            result_mock.scalar_one_or_none.return_value = None
        elif "metadata_profiles" in stmt_str:
            result_mock.scalar_one_or_none.return_value = None
        elif "job_stage_history" in stmt_str:
            result_mock.scalars.return_value.all.return_value = []
        return result_mock

    def custom_get(model_class, ident):
        if model_class == Job:
            return job
        elif model_class == ArtifactRecord:
            return mock_art
        return None

    original_execute = mock_db.execute
    original_get = mock_db.get
    
    mock_db.execute = custom_execute
    mock_db.get = custom_get
    
    try:
        response = client.get(f"/jobs/{job_uuid}/details")
        assert response.status_code == 200
        details = response.json()
        
        # Verify artifact and data quality report
        assert len(details["artifacts"]) == 1
        artifact_detail = details["artifacts"][0]
        assert artifact_detail["artifact_id"] == str(artifact_uuid)
        assert artifact_detail["data_quality"] is not None
        assert artifact_detail["data_quality"]["status"] == "PASSED"
        assert artifact_detail["data_quality"]["rules_executed"] == 5
        assert artifact_detail["data_quality"]["report_json"] == {"summary": "passed"}
    finally:
        mock_db.execute = original_execute
        mock_db.get = original_get

