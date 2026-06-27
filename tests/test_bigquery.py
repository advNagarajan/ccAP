import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.db.source import Source
from app.models.domain.artifact import Artifact
from app.connectors.bigquery_connector import BigQueryConnector


@pytest.fixture
def mock_source():
    return Source(
        source_id="b041cfb2-1324-4eb9-a799-a4195152865c",
        name="BigQuery Test Source",
        source_type="BIGQUERY",
        connection_details={
            "dataset": "test_dataset",
            "table": "test_table",
            "project_id": "test-project",
            "credentials_json": {"type": "service_account"}
        },
        status="ACTIVE"
    )


@patch.object(BigQueryConnector, "_get_client")
def test_list_artifacts_success(mock_get_client, mock_source):
    mock_table = MagicMock()
    mock_table.num_rows = 5000
    mock_time = datetime(2026, 6, 21, 13, 20, 0, tzinfo=timezone.utc)
    mock_table.modified = mock_time

    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_client.get_table.return_value = mock_table
    mock_get_client.return_value = mock_client

    connector = BigQueryConnector()
    artifacts = connector.list_artifacts(mock_source)

    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert artifact.artifact_name == "test_table"
    assert artifact.last_modified == mock_time.isoformat()
    assert artifact.external_id == f"test_dataset:test_table:{int(mock_time.timestamp())}"

    assert artifact.metadata["dataset"] == "test_dataset"
    assert artifact.metadata["table"] == "test_table"
    assert artifact.metadata["num_rows"] == 5000
    assert artifact.metadata["etag"] == artifact.external_id

    mock_client.get_table.assert_called_once_with("test-project.test_dataset.test_table")


@patch.object(BigQueryConnector, "_get_client")
def test_list_artifacts_error(mock_get_client, mock_source):
    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_client.get_table.side_effect = Exception("BigQuery table not found")
    mock_get_client.return_value = mock_client

    connector = BigQueryConnector()
    artifacts = connector.list_artifacts(mock_source)

    assert len(artifacts) == 0


@patch.object(BigQueryConnector, "_get_client")
def test_extract_sample(mock_get_client, mock_source):
    mock_row1 = {"id": 1, "name": "Alice"}
    mock_row2 = {"id": 2, "name": "Bob"}

    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_get_client.return_value = mock_client

    # Mock query job result
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row1, mock_row2]
    mock_client.query.return_value = mock_query_job

    artifact = Artifact(
        external_id="test_dataset:test_table:12345",
        artifact_name="test_table",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "dataset": "test_dataset",
            "table": "test_table",
            "last_modified": "2026-06-21T13:20:00Z",
            "num_rows": 5000
        }
    )

    connector = BigQueryConnector()
    raw_data = connector.extract_sample(mock_source, artifact)

    assert raw_data.format_type == "JSON"
    assert raw_data.source_type == "BIGQUERY"
    assert raw_data.source_name == "test_table"

    parsed_content = json.loads(raw_data.content)
    assert isinstance(parsed_content, list)
    assert len(parsed_content) == 2
    assert parsed_content[0] == {"id": 1, "name": "Alice"}

    assert raw_data.connector_metadata["sampled_count"] == 2
    mock_client.query.assert_called_once_with("SELECT * FROM `test-project.test_dataset.test_table` LIMIT 1000")


@patch.object(BigQueryConnector, "_get_client")
def test_extract_full_without_sampling(mock_get_client, mock_source):
    mock_row = {"id": 100, "name": "Charlie"}

    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_get_client.return_value = mock_client

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = [mock_row]
    mock_client.query.return_value = mock_query_job

    artifact = Artifact(
        external_id="test_dataset:test_table:12345",
        artifact_name="test_table",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "dataset": "test_dataset",
            "table": "test_table",
            "last_modified": "2026-06-21T13:20:00Z",
            "num_rows": 5000
        }
    )

    connector = BigQueryConnector()
    raw_data = connector.extract_full(mock_source, artifact)

    assert raw_data.format_type == "JSON"
    assert json.loads(raw_data.content) == [{"id": 100, "name": "Charlie"}]
    mock_client.query.assert_called_once_with("SELECT * FROM `test-project.test_dataset.test_table`")


@patch.object(BigQueryConnector, "_get_client")
def test_extract_full_with_sampling(mock_get_client, mock_source):
    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_get_client.return_value = mock_client

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = []
    mock_client.query.return_value = mock_query_job

    artifact = Artifact(
        external_id="test_dataset:test_table:12345",
        artifact_name="test_table",
        last_modified="2026-06-21T13:20:00Z",
        metadata={
            "dataset": "test_dataset",
            "table": "test_table",
            "last_modified": "2026-06-21T13:20:00Z",
            "num_rows": 5000
        }
    )

    connector = BigQueryConnector()
    
    # 1. Test standard sampling (limit = 5000 * 0.1 = 500)
    connector.extract_full(mock_source, artifact, sample_ratio=0.1, random_sample=False)
    mock_client.query.assert_any_call("SELECT * FROM `test-project.test_dataset.test_table` LIMIT 500")

    # 2. Test random sampling (limit = 5000 * 0.05 = 250)
    connector.extract_full(mock_source, artifact, sample_ratio=0.05, random_sample=True)
    mock_client.query.assert_any_call("SELECT * FROM `test-project.test_dataset.test_table` ORDER BY RAND() LIMIT 250")


@patch.object(BigQueryConnector, "_get_client")
def test_get_artifact_success(mock_get_client, mock_source):
    mock_table = MagicMock()
    mock_table.num_rows = 5000
    mock_time = datetime(2026, 6, 21, 13, 20, 0, tzinfo=timezone.utc)
    mock_table.modified = mock_time

    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_client.get_table.return_value = mock_table
    mock_get_client.return_value = mock_client

    connector = BigQueryConnector()
    artifact = connector.get_artifact(mock_source, "test_dataset:test_table:12345")

    assert artifact is not None
    assert artifact.artifact_name == "test_table"
    assert artifact.metadata["dataset"] == "test_dataset"
    assert artifact.metadata["table"] == "test_table"


@patch.object(BigQueryConnector, "_get_client")
def test_get_artifact_not_found(mock_get_client, mock_source):
    mock_client = MagicMock()
    mock_client.project = "test-project"
    mock_client.get_table.side_effect = Exception("BigQuery table not found")
    mock_get_client.return_value = mock_client

    connector = BigQueryConnector()
    artifact = connector.get_artifact(mock_source, "test_dataset:test_table:12345")

    assert artifact is None


def test_get_artifact_invalid_id(mock_source):
    connector = BigQueryConnector()
    artifact = connector.get_artifact(mock_source, "invalid_id_no_colon")
    assert artifact is None


@patch("app.connectors.bigquery_connector.service_account.Credentials.from_service_account_info")
@patch("app.connectors.bigquery_connector.bigquery.Client")
def test_get_client_success(mock_client_class, mock_credentials_class):
    connection_details = {
        "dataset": "test_dataset",
        "table": "test_table",
        "project_id": "test-project",
        "credentials_json": {"dummy_key": "dummy_value"}
    }

    connector = BigQueryConnector()
    connector._get_client(connection_details)

    mock_credentials_class.assert_called_once_with({"dummy_key": "dummy_value"})
    mock_client_class.assert_called_once_with(
        project="test-project",
        credentials=mock_credentials_class.return_value
    )


def test_get_client_validation_errors():
    connector = BigQueryConnector()

    with pytest.raises(ValueError, match="Missing 'credentials_json'"):
        connector._get_client({"project_id": "test"})

    with pytest.raises(ValueError, match="Missing 'project_id'"):
        connector._get_client({"credentials_json": {"some": "info"}})
