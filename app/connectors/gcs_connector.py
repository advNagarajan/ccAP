from google.cloud import storage
from google.oauth2 import service_account

from app.connectors.base import BaseConnector

from app.models.domain.artifact import Artifact
from app.models.domain.raw_data import RawData

from app.services.artifact_service import (
    discover_new_artifacts,
    get_unprocessed_artifacts
)

from app.core.settings import settings

class GCSConnector(BaseConnector):

    def _get_client(self, connection_details) -> storage.Client:
        project_id = connection_details.get("project_id")
        credentials_dict = connection_details.get("credentials_json")

        if not credentials_dict:
            raise ValueError(
                "Missing 'credentials_json' in connection details. "
                "A user service account is required to connect to the external GCS bucket."
            )
        if not project_id:
            raise ValueError(
                "Missing 'project_id' in connection details. "
                "A GCP project ID is required to connect to the external GCS bucket."
            )

        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return storage.Client(
            project=project_id,
            credentials=credentials
        )

    def list_artifacts(
        self,
        source
    ) -> list[Artifact]:

        connection_details = source.connection_details

        bucket_name = connection_details["bucket"]
        prefix = connection_details["prefix"]

        client = self._get_client(connection_details)

        blobs = client.list_blobs(
            bucket_name,
            prefix=prefix
        )

        artifacts = []

        for blob in blobs:

            if blob.name.endswith("/"):
                continue

            artifacts.append(
                Artifact(
                    external_id=f"{blob.name}:{blob.generation}",
                    artifact_name=blob.name,
                    last_modified=blob.updated.isoformat(),
                    metadata={
                        "bucket": bucket_name,
                        "object_name": blob.name,
                        "generation": str(blob.generation),
                        "size": blob.size,
                        "etag": blob.etag
                    }
                )
            )

        return artifacts

    def get_unprocessed_artifacts(
        self,
        source,
        artifacts,
        db
    ) -> list[Artifact]:

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

    def extract_sample(
        self,
        source,
        artifact: Artifact
    ) -> RawData:

        bucket_name = artifact.metadata["bucket"]

        object_name = artifact.metadata["object_name"]

        client = self._get_client(source.connection_details)

        bucket = client.bucket(bucket_name)

        blob = bucket.blob(object_name)

        content = blob.download_as_text()

        format_type = object_name.split(".")[-1].upper()

        return RawData(
            content=content,
            format_type=format_type,
            source_type=source.source_type,
            source_name=object_name,
            connector_metadata=artifact.metadata
        )


    def extract_full(
        self,
        source,
        artifact: Artifact
    ) -> RawData:

        bucket_name = artifact.metadata["bucket"]

        object_name = artifact.metadata["object_name"]

        client = self._get_client(source.connection_details)

        bucket = client.bucket(bucket_name)

        blob = bucket.blob(object_name)

        content = blob.download_as_text()

        format_type = object_name.split(".")[-1].upper()

        return RawData(
            content=content,
            format_type=format_type,
            source_type=source.source_type,
            source_name=object_name,
            connector_metadata=artifact.metadata
        )


    def get_artifact(
        self,
        source,
        artifact_external_id: str
    ) -> Artifact | None:

        object_name = artifact_external_id.split(":")[0]

        connection_details = source.connection_details

        bucket_name = connection_details["bucket"]

        client = self._get_client(connection_details)

        bucket = client.bucket(bucket_name)

        blob = bucket.get_blob(object_name)

        if blob is None:
            return None

        return Artifact(
            external_id=f"{blob.name}:{blob.generation}",
            artifact_name=blob.name,
            last_modified=blob.updated.isoformat(),
            metadata={
                "bucket": bucket_name,
                "object_name": blob.name,
                "generation": str(blob.generation),
                "size": blob.size,
                "etag": blob.etag
            }
        )