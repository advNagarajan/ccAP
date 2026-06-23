import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db
from app.models.db.job import Job
from app.models.db.artifact_record import ArtifactRecord
from app.constants.job_status import JobStatus

# Create mock DB session
mock_db = MagicMock()

def mock_add(instance):
    if isinstance(instance, Job):
        if not getattr(instance, "job_id", None):
            instance.job_id = uuid.uuid4()
        if not getattr(instance, "created_at", None):
            instance.created_at = datetime.utcnow()
        if not getattr(instance, "updated_at", None):
            instance.updated_at = datetime.utcnow()
        if not getattr(instance, "retry_count", None):
            instance.retry_count = 0

mock_db.add = MagicMock(side_effect=mock_add)

def override_get_db():
    try:
        yield mock_db
    finally:
        pass

@pytest.fixture(autouse=True)
def reset_mock_db():
    mock_db.reset_mock()
    mock_db.add = MagicMock(side_effect=mock_add)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

@patch("app.api.job_routes.publish_ingestion_requested")
@patch("app.api.job_routes.start_stage")
def test_retry_job_not_found(mock_start_stage, mock_publish):
    # Setup database Mock
    mock_db.get.side_effect = None
    mock_db.get.return_value = None

    response = client.post(f"/jobs/{uuid.uuid4()}/retry")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


@patch("app.api.job_routes.publish_ingestion_requested")
@patch("app.api.job_routes.start_stage")
def test_retry_job_not_failed(mock_start_stage, mock_publish):
    # Setup failed job status logic
    job_id = uuid.uuid4()
    mock_job = Job(
        job_id=job_id,
        source_id=uuid.uuid4(),
        status=JobStatus.COMPLETED,
        parent_job_id=None
    )
    mock_db.get.side_effect = None
    mock_db.get.return_value = mock_job

    response = client.post(f"/jobs/{job_id}/retry")
    assert response.status_code == 400
    assert "Only failed jobs can be retried" in response.json()["detail"]


@patch("app.api.job_routes.publish_ingestion_requested")
@patch("app.api.job_routes.start_stage")
def test_retry_job_success(mock_start_stage, mock_publish):
    job_id = uuid.uuid4()
    source_id = uuid.uuid4()
    
    # Mocking old failed job
    old_job = Job(
        job_id=job_id,
        source_id=source_id,
        status=JobStatus.FAILED,
        parent_job_id=None,
        retry_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    # Mock lookup
    def mock_get(model_class, ident):
        if model_class == Job:
            return old_job
        return MagicMock()

    mock_db.get.side_effect = mock_get
    mock_db.get.return_value = None
    mock_db.execute.return_value = MagicMock()
    
    # Mock stage creation
    mock_stage = MagicMock()
    mock_stage.stage_history_id = uuid.uuid4()
    mock_start_stage.return_value = mock_stage

    # Call endpoint
    response = client.post(f"/jobs/{job_id}/retry")
    assert response.status_code == 201
    
    data = response.json()
    assert data["status"] == JobStatus.RECEIVED
    assert data["source_id"] == str(source_id)
    assert data["parent_job_id"] == str(job_id)

    # Ensure old job transitioned to RETRIED
    assert old_job.status == JobStatus.RETRIED

    # Ensure DB interactions occurred
    assert mock_db.add.call_count == 2
    mock_db.commit.assert_called()
    mock_publish.assert_called_once()


@patch("app.api.job_routes.publish_ingestion_requested")
@patch("app.api.job_routes.start_stage")
def test_retry_job_max_limit_exceeded(mock_start_stage, mock_publish):
    # Grandparent Job (Job A)
    grandparent_id = uuid.uuid4()
    grandparent_job = Job(
        job_id=grandparent_id,
        source_id=uuid.uuid4(),
        status=JobStatus.FAILED,
        parent_job_id=None
    )
    
    # Parent Job (Job B - Retry #1)
    parent_id = uuid.uuid4()
    parent_job = Job(
        job_id=parent_id,
        source_id=grandparent_job.source_id,
        status=JobStatus.FAILED,
        parent_job_id=grandparent_id
    )

    # Failed Job (Job C - Retry #2)
    failed_id = uuid.uuid4()
    failed_job = Job(
        job_id=failed_id,
        source_id=grandparent_job.source_id,
        status=JobStatus.FAILED,
        parent_job_id=parent_id
    )

    # Mock DB get hierarchy lookup
    def mock_get_job(model_class, ident):
        if model_class == Job:
            if ident == failed_id:
                return failed_job
            elif ident == parent_id:
                return parent_job
            elif ident == grandparent_id:
                return grandparent_job
        return None

    mock_db.get.side_effect = mock_get_job

    # Attempting to trigger Retry #3 (exceeds max limit 2)
    response = client.post(f"/jobs/{failed_id}/retry")
    assert response.status_code == 400
    assert "Maximum retry limit (2) reached" in response.json()["detail"]


def test_kill_job_not_found():
    mock_db.get.side_effect = None
    mock_db.get.return_value = None

    response = client.post(f"/jobs/{uuid.uuid4()}/kill")
    assert response.status_code == 404
    assert "Job not found" in response.json()["detail"]


def test_kill_job_invalid_status():
    job_id = uuid.uuid4()
    mock_job = Job(
        job_id=job_id,
        source_id=uuid.uuid4(),
        status=JobStatus.COMPLETED,
        parent_job_id=None,
        retry_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    mock_db.get.side_effect = None
    mock_db.get.return_value = mock_job

    response = client.post(f"/jobs/{job_id}/kill")
    assert response.status_code == 400
    assert "Cannot kill a job" in response.json()["detail"]


def test_kill_job_success():
    job_id = uuid.uuid4()
    mock_job = Job(
        job_id=job_id,
        source_id=uuid.uuid4(),
        status=JobStatus.FAILED,
        parent_job_id=None,
        retry_count=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    mock_db.get.side_effect = None
    mock_db.get.return_value = mock_job
    mock_db.execute.return_value = MagicMock()

    response = client.post(f"/jobs/{job_id}/kill")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == JobStatus.CANCELLED
    assert mock_job.status == JobStatus.CANCELLED
    assert "manually terminated" in mock_job.error_message

    mock_db.commit.assert_called()
