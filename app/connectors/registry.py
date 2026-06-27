from app.connectors.gcs_connector import GCSConnector
from app.connectors.firestore_connector import FirestoreConnector
from app.connectors.bigquery_connector import BigQueryConnector


CONNECTORS = {
    "GCS": GCSConnector(),
    "FIRESTORE": FirestoreConnector(),
    "BIGQUERY": BigQueryConnector()
}