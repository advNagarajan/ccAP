from app.connectors.gcs_connector import GCSConnector
from app.connectors.firestore_connector import FirestoreConnector


CONNECTORS = {
    "GCS": GCSConnector(),
    "FIRESTORE": FirestoreConnector()
}