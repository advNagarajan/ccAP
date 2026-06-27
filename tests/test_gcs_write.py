from unittest.mock import MagicMock, patch, ANY
import pytest
from app.connectors.gcs_connector import GCSConnector


@pytest.fixture
def mock_connection():
    return {
        "bucket": "test-lake-bucket",
        "prefix": "raw_ingest",
        "project_id": "test-project",
        "credentials_json": {"type": "service_account"}
    }


@patch.object(GCSConnector, "_get_client")
def test_gcs_write_overwrite_json(mock_get_client, mock_connection):
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()
    
    mock_get_client.return_value = mock_client
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    connector = GCSConnector()
    connector.write_data(
        connection_details=mock_connection,
        data=[{"id": 1, "value": "A"}],
        format_type="JSON",
        table_name="customers.json",
        write_mode="OVERWRITE"
    )

    mock_client.bucket.assert_called_once_with("test-lake-bucket")
    mock_bucket.blob.assert_called_once_with("raw_ingest/customers.json")
    mock_blob.upload_from_string.assert_called_once_with(
        '[{"id": 1, "value": "A"}]',
        content_type="application/json"
    )


@patch.object(GCSConnector, "_get_client")
def test_gcs_write_append_csv(mock_get_client, mock_connection):
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    connector = GCSConnector()
    connector.write_data(
        connection_details=mock_connection,
        data="id,val\n1,Hello",
        format_type="CSV",
        table_name="orders.csv",
        write_mode="APPEND"
    )

    mock_bucket.blob.assert_called_once()
    called_path = mock_bucket.blob.call_args[0][0]
    
    assert called_path.startswith("raw_ingest/orders_part_")
    assert called_path.endswith(".csv")
    mock_blob.upload_from_string.assert_called_once_with(
        "id,val\n1,Hello",
        content_type="text/csv"
    )


@patch.object(GCSConnector, "_get_client")
def test_gcs_write_records_csv_conversion(mock_get_client, mock_connection):
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_blob = MagicMock()

    mock_get_client.return_value = mock_client
    mock_client.bucket.return_value = mock_bucket
    mock_bucket.blob.return_value = mock_blob

    connector = GCSConnector()
    connector.write_data(
        connection_details=mock_connection,
        data=[{"col1": "x", "col2": "y"}],
        format_type="CSV",
        table_name="data.csv",
        write_mode="OVERWRITE"
    )

    mock_blob.upload_from_string.assert_called_once()
    uploaded_data = mock_blob.upload_from_string.call_args[0][0]
    assert "col1,col2" in uploaded_data
    assert "x,y" in uploaded_data
