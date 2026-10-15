from app.connectors.gcs_connector import GCSConnector
from app.connectors.firestore_connector import FirestoreConnector
from app.connectors.bigquery_connector import BigQueryConnector
from app.connectors.s3_connector import S3Connector


CONNECTORS = {
    "GCS": GCSConnector(),
    "FIRESTORE": FirestoreConnector(),
    "BIGQUERY": BigQueryConnector(),
    "S3": S3Connector()
}