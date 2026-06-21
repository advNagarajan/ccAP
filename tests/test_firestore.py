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
    mock_doc.to_dict.return_value = {"field1": "value1", "field2": 123}

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.stream.return_value = [mock_doc]

    connector = FirestoreConnector()
    artifacts = connector.list_artifacts(mock_source)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_name == "doc1"
    assert artifact.last_modified == mock_time.isoformat()
    assert artifact.external_id.startswith("doc1:")
    
    assert artifact.metadata["collection"] == "test_collection"
    assert artifact.metadata["document_id"] == "doc1"
    assert artifact.metadata["object_name"] == "doc1"
    assert artifact.metadata["update_time"] == mock_time.isoformat()
    assert "size" in artifact.metadata
    assert artifact.metadata["etag"] == artifact.external_id


@patch.object(FirestoreConnector, "_get_client")
def test_extract_sample_success(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.exists = True
    mock_doc.to_dict.return_value = {"name": "Alice", "age": 30}

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

    artifact = Artifact(
        external_id="doc1:12345",
        artifact_name="doc1",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "collection": "test_collection",
            "document_id": "doc1",
            "object_name": "doc1",
            "update_time": "2026-06-21T13:20:00Z"
        }
    )

    connector = FirestoreConnector()
    raw_data = connector.extract_sample(mock_source, artifact)

    assert raw_data.format_type == "JSON"
    assert raw_data.source_type == "FIRESTORE"
    assert raw_data.source_name == "doc1"
    
    parsed_content = json.loads(raw_data.content)
    assert parsed_content == {"name": "Alice", "age": 30}


@patch.object(FirestoreConnector, "_get_client")
def test_extract_sample_not_found(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

    artifact = Artifact(
        external_id="doc1:12345",
        artifact_name="doc1",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "collection": "test_collection",
            "document_id": "doc1"
        }
    )

    connector = FirestoreConnector()
    with pytest.raises(Exception, match="not found"):
        connector.extract_sample(mock_source, artifact)


@patch.object(FirestoreConnector, "_get_client")
def test_get_artifact_success(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.id = "doc1"
    mock_doc.exists = True
    mock_time = datetime(2026, 6, 21, 13, 20, 0, tzinfo=timezone.utc)
    mock_doc.update_time = mock_time
    mock_doc.to_dict.return_value = {"key": "val"}

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

    connector = FirestoreConnector()
    artifact = connector.get_artifact(mock_source, "doc1:1234567")

    assert artifact is not None
    assert artifact.artifact_name == "doc1"
    assert artifact.metadata["document_id"] == "doc1"
    assert artifact.metadata["collection"] == "test_collection"


@patch.object(FirestoreConnector, "_get_client")
def test_get_artifact_not_found(mock_get_client, mock_source):
    mock_doc = MagicMock()
    mock_doc.exists = False

    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.collection.return_value.document.return_value.get.return_value = mock_doc

    connector = FirestoreConnector()
    artifact = connector.get_artifact(mock_source, "doc1:1234567")

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
