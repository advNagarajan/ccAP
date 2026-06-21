import json
from google.cloud import firestore
from google.oauth2 import service_account

from app.connectors.base import BaseConnector
from app.models.domain.artifact import Artifact
from app.models.domain.raw_data import RawData
from app.services.artifact_service import (
    discover_new_artifacts,
    get_unprocessed_artifacts
)
from app.core.settings import settings


class FirestoreConnector(BaseConnector):

    def _get_client(self, connection_details) -> firestore.Client:
        project_id = connection_details.get("project_id")
        database = connection_details.get("database")
        credentials_dict = connection_details.get("credentials_json")

        if not credentials_dict:
            raise ValueError(
                "Missing 'credentials_json' in connection details. "
                "A user service account is required to connect to the external Firestore instance."
            )
        if not project_id:
            raise ValueError(
                "Missing 'project_id' in connection details. "
                "A GCP project ID is required to connect to the external Firestore instance."
            )

        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return firestore.Client(
            project=project_id,
            database=database,
            credentials=credentials
        )

    def list_artifacts(self, source) -> list[Artifact]:
        connection_details = source.connection_details
        collection_name = connection_details["collection"]

        client = self._get_client(connection_details)
        docs = client.collection(collection_name).stream()

        artifacts = []
        for doc in docs:
            update_time = doc.update_time
            update_time_iso = update_time.isoformat()
            
            try:
                version_suffix = f"{update_time.timestamp_pb().seconds}_{update_time.timestamp_pb().nanoseconds}"
            except AttributeError:
                version_suffix = f"{int(update_time.timestamp())}"

            external_id = f"{doc.id}:{version_suffix}"

            doc_dict = doc.to_dict()
            size_bytes = len(json.dumps(doc_dict, default=str))

            artifacts.append(
                Artifact(
                    external_id=external_id,
                    artifact_name=doc.id,
                    last_modified=update_time_iso,
                    metadata={
                        "collection": collection_name,
                        "document_id": doc.id,
                        "object_name": doc.id,
                        "update_time": update_time_iso,
                        "size": size_bytes,
                        "etag": f"{doc.id}:{version_suffix}"
                    }
                )
            )

        return artifacts

    def get_unprocessed_artifacts(self, source, artifacts, db) -> list[Artifact]:
        discover_new_artifacts(
            source.source_id,
            artifacts,
            db
        )
        return get_unprocessed_artifacts(
            source.source_id,
            artifacts,
            db
        )

    def extract_sample(self, source, artifact: Artifact) -> RawData:
        collection_name = artifact.metadata["collection"]
        document_id = artifact.metadata["document_id"]

        client = self._get_client(source.connection_details)
        doc_ref = client.collection(collection_name).document(document_id)
        doc = doc_ref.get()

        if not doc.exists:
            raise Exception(f"Document {document_id} not found in collection {collection_name}")

        doc_dict = doc.to_dict()
        content = json.dumps(doc_dict, default=str)

        return RawData(
            content=content,
            format_type="JSON",
            source_type=source.source_type,
            source_name=document_id,
            connector_metadata=artifact.metadata
        )

    def extract_full(self, source, artifact: Artifact) -> RawData:
        return self.extract_sample(source, artifact)

    def get_artifact(self, source, artifact_external_id: str) -> Artifact | None:
        if ":" not in artifact_external_id:
            return None
            
        document_id = artifact_external_id.split(":")[0]
        connection_details = source.connection_details
        collection_name = connection_details["collection"]

        client = self._get_client(connection_details)
        doc_ref = client.collection(collection_name).document(document_id)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        update_time = doc.update_time
        update_time_iso = update_time.isoformat()
        
        try:
            version_suffix = f"{update_time.timestamp_pb().seconds}_{update_time.timestamp_pb().nanoseconds}"
        except AttributeError:
            version_suffix = f"{int(update_time.timestamp())}"

        doc_dict = doc.to_dict()
        size_bytes = len(json.dumps(doc_dict, default=str))

        return Artifact(
            external_id=f"{doc.id}:{version_suffix}",
            artifact_name=doc.id,
            last_modified=update_time_iso,
            metadata={
                "collection": collection_name,
                "document_id": doc.id,
                "object_name": doc.id,
                "update_time": update_time_iso,
                "size": size_bytes,
                "etag": f"{doc.id}:{version_suffix}"
            }
        )
