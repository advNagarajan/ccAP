CONNECTORS = {}

# AWS S3 Connector
try:
    from app.connectors.s3_connector import S3Connector
    CONNECTORS["S3"] = S3Connector()
except Exception:
    pass

# Google Cloud Storage Connector
try:
    from app.connectors.gcs_connector import GCSConnector
    CONNECTORS["GCS"] = GCSConnector()
except Exception:
    pass

# Firestore Connector
try:
    from app.connectors.firestore_connector import FirestoreConnector
    CONNECTORS["FIRESTORE"] = FirestoreConnector()
except Exception:
    pass

# BigQuery Connector
try:
    from app.connectors.bigquery_connector import BigQueryConnector
    CONNECTORS["BIGQUERY"] = BigQueryConnector()
except Exception:
    pass