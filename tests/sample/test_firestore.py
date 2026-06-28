import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.db.source import Source
from app.models.domain.artifact import Artifact
from app.connectors.firestore_connector import FirestoreConnector


@pytest.fixture
def mock_source():
    return Source(
        source_id="d3b07384-d113-4ec6-a70d-45e0d45bf691",
        name="Firestore Test Source",
        source_type="FIRESTORE",
        connection_details={
            "collection": "test_collection",
            "project_id": "test-project",
            "credentials_json": {"type": "service_account"}
        },
        status="ACTIVE"
    )


@patch.object(FirestoreConnector, "_get_client")
def test_list_artifacts(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.id = "doc1"
    mock_time = datetime(2026, 6, 21, 13, 20, 0, tzinfo=timezone.utc)
    mock_doc.update_time = mock_time

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.select.return_value.stream.return_value = [mock_doc]

    connector = FirestoreConnector()
    artifacts = connector.list_artifacts(mock_source)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_name == "test_collection"
    assert artifact.last_modified == mock_time.isoformat()
    assert artifact.external_id.startswith("test_collection:")
    
    assert artifact.metadata["collection"] == "test_collection"
    assert artifact.metadata["object_name"] == "test_collection"
    assert artifact.metadata["update_time"] == mock_time.isoformat()
    assert artifact.metadata["etag"] == artifact.external_id


@patch.object(FirestoreConnector, "_get_client")
def test_extract_sample_success(mock_get_client, mock_source):
    # Mock document references / snapshots
    mock_doc_snap1 = MagicMock()
    mock_doc_snap1.reference = "ref1"
    mock_doc_snap2 = MagicMock()
    mock_doc_snap2.reference = "ref2"

    mock_doc1 = MagicMock()
    mock_doc1.exists = True
    mock_doc1.to_dict.return_value = {"name": "Alice", "info": {"age": 30}}
    mock_doc2 = MagicMock()
    mock_doc2.exists = True
    mock_doc2.to_dict.return_value = {"name": "Bob", "info": {"location": "NY"}}

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.select.return_value.stream.return_value = [mock_doc_snap1, mock_doc_snap2]
    mock_client.get_all.return_value = [mock_doc1, mock_doc2]

    artifact = Artifact(
        external_id="test_collection:12345",
        artifact_name="test_collection",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "collection": "test_collection",
            "object_name": "test_collection",
            "update_time": "2026-06-21T13:20:00Z"
        }
    )

    connector = FirestoreConnector()
    raw_data = connector.extract_sample(mock_source, artifact)

    assert raw_data.format_type == "JSON"
    assert raw_data.source_type == "FIRESTORE"
    assert raw_data.source_name == "test_collection"
    
    parsed_content = json.loads(raw_data.content)
    assert isinstance(parsed_content, list)
    assert len(parsed_content) == 2
    assert parsed_content[0] == {"name": "Alice", "info": {"age": 30}}

    assert raw_data.connector_metadata["sampled_count"] == 2


def test_extract_metadata_frequencies():
    from app.models.domain.dataset import Dataset
    from app.services.metadata_service import extract_metadata

    records = [
        {"name": "Alice", "info": {"age": 30}},
        {"name": "Bob", "info": {"location": "NY"}}
    ]

    # Test JSON dataset - should calculate frequencies
    dataset_json = Dataset(records=records, source_type="FIRESTORE", format_type="JSON")
    metadata_json = extract_metadata(dataset_json, {})

    freq = metadata_json.field_frequencies
    assert freq["name"] == 2
    assert freq["info"] == 2
    assert freq["info.age"] == 1
    assert freq["info.location"] == 1

    # Test CSV dataset - should NOT calculate frequencies
    dataset_csv = Dataset(records=records, source_type="GCS", format_type="CSV")
    metadata_csv = extract_metadata(dataset_csv, {})

    assert metadata_csv.field_frequencies == {}


@patch.object(FirestoreConnector, "_get_previous_update_time")
@patch.object(FirestoreConnector, "_get_client")
def test_extract_full_incremental(mock_get_client, mock_prev_time, mock_source):
    # Set previous update time
    mock_prev_time.return_value = datetime(2026, 6, 21, 13, 0, 0, tzinfo=timezone.utc)

    # Document 1 (older, should be skipped)
    mock_doc1 = MagicMock()
    mock_doc1.update_time = datetime(2026, 6, 21, 12, 59, 0, tzinfo=timezone.utc)
    mock_doc1.to_dict.return_value = {"name": "Old Document"}

    # Document 2 (newer, should be extracted)
    mock_doc2 = MagicMock()
    mock_doc2.update_time = datetime(2026, 6, 21, 13, 1, 0, tzinfo=timezone.utc)
    mock_doc2.to_dict.return_value = {"name": "New Document"}

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.stream.return_value = [mock_doc1, mock_doc2]

    artifact = Artifact(
        external_id="test_collection:12345",
        artifact_name="test_collection",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "collection": "test_collection",
            "object_name": "test_collection",
            "update_time": "2026-06-21T13:20:00Z"
        }
    )

    connector = FirestoreConnector()
    raw_data = connector.extract_full(mock_source, artifact)

    parsed_content = json.loads(raw_data.content)
    assert isinstance(parsed_content, list)
    assert len(parsed_content) == 1
    assert parsed_content[0] == {"name": "New Document"}


@patch.object(FirestoreConnector, "_get_client")
def test_get_artifact_success(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.id = "doc1"
    mock_time = datetime(2026, 6, 21, 13, 20, 0, tzinfo=timezone.utc)
    mock_doc.update_time = mock_time

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.select.return_value.stream.return_value = [mock_doc]

    connector = FirestoreConnector()
    artifact = connector.get_artifact(mock_source, "test_collection:1234567")

    assert artifact is not None
    assert artifact.artifact_name == "test_collection"
    assert artifact.metadata["collection"] == "test_collection"


@patch.object(FirestoreConnector, "_get_client")
def test_get_artifact_not_found(mock_get_client, mock_source):
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.select.return_value.stream.return_value = []

    connector = FirestoreConnector()
    artifact = connector.get_artifact(mock_source, "test_collection:1234567")

    assert artifact is None


def test_get_artifact_invalid_id(mock_source):
    connector = FirestoreConnector()
    artifact = connector.get_artifact(mock_source, "invalid_id_no_colon")
    assert artifact is None


@patch("app.connectors.firestore_connector.service_account.Credentials.from_service_account_info")
@patch("app.connectors.firestore_connector.firestore.Client")
def test_get_client_custom_credentials(mock_client_class, mock_credentials_class):
    connection_details = {
        "collection": "test_collection",
        "project_id": "custom-project",
        "database": "custom-db",
        "credentials_json": {"dummy_key": "dummy_value"}
    }

    connector = FirestoreConnector()
    connector._get_client(connection_details)

    mock_credentials_class.assert_called_once_with({"dummy_key": "dummy_value"})
    mock_client_class.assert_called_once_with(
        project="custom-project",
        database="custom-db",
        credentials=mock_credentials_class.return_value
    )


def test_get_client_missing_credentials():
    connector = FirestoreConnector()
    
    with pytest.raises(ValueError, match="Missing 'credentials_json'"):
        connector._get_client({"collection": "test", "project_id": "proj"})

    with pytest.raises(ValueError, match="Missing 'project_id'"):
        connector._get_client({"collection": "test", "credentials_json": {"some": "info"}})


@patch("app.connectors.firestore_connector.SessionLocal")
def test_get_previous_update_time(mock_session_cls):
    mock_session = MagicMock()
    mock_session_cls.return_value = mock_session
    
    mock_record = MagicMock()
    mock_record.artifact_metadata = {"update_time": "2026-06-21T13:20:00Z"}
    
    mock_session.execute.return_value.scalars.return_value.first.return_value = mock_record

    connector = FirestoreConnector()
    prev_time = connector._get_previous_update_time("source-uuid")

    assert prev_time is not None
    assert prev_time.isoformat() == "2026-06-21T13:20:00+00:00"
