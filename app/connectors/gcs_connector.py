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
        artifact: Artifact,
        sample_ratio: float | None = None,
        random_sample: bool = False
    ) -> RawData:

        bucket_name = artifact.metadata["bucket"]

        object_name = artifact.metadata["object_name"]

        client = self._get_client(source.connection_details)

        bucket = client.bucket(bucket_name)

        blob = bucket.blob(object_name)

        content = blob.download_as_text()

        format_type = object_name.split(".")[-1].upper()

        if sample_ratio is not None:
            import random
            import json
            import csv
            from io import StringIO
            from app.parsers.registry import PARSERS

            parser = PARSERS.get(format_type)
            if parser is None:
                raise Exception(f"No parser registered for {format_type}")

            full_raw = RawData(
                content=content,
                format_type=format_type,
                source_type=source.source_type,
                source_name=object_name,
                connector_metadata=artifact.metadata
            )
            dataset = parser.parse(full_raw)
            
            k = max(1, int(len(dataset.records) * sample_ratio))
            if random_sample:
                sampled_records = random.sample(dataset.records, min(len(dataset.records), k))
            else:
                sampled_records = dataset.records[:k]

            if format_type == "CSV":
                output = StringIO()
                if sampled_records:
                    headers = list(sampled_records[0].keys())
                    writer = csv.DictWriter(output, fieldnames=headers)
                    writer.writeheader()
                    writer.writerows(sampled_records)
                content = output.getvalue()
            else:
                content = json.dumps(sampled_records, default=str)

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

    def write_data(
        self,
        connection_details: dict,
        data: list[dict] | str | bytes,
        format_type: str,
        table_name: str,
        write_mode: str = "APPEND",
        key_columns: list[str] | None = None
    ) -> None:
        client = self._get_client(connection_details)
        bucket_name = connection_details["bucket"]
        prefix = connection_details.get("prefix", "").strip()

        bucket = client.bucket(bucket_name)

        # Build path
        object_name = f"{prefix}/{table_name}" if prefix else table_name

        if write_mode.upper() == "APPEND":
            import time
            import uuid
            if "." in table_name:
                base, ext = table_name.rsplit(".", 1)
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
                object_name = f"{prefix}/{base}{suffix}" if prefix else f"{base}{suffix}"
            else:
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                object_name = f"{object_name}{suffix}"

        blob = bucket.blob(object_name)

        if isinstance(data, str):
            content_type = "text/csv" if format_type.upper() == "CSV" else "application/json"
            blob.upload_from_string(data, content_type=content_type)
        elif isinstance(data, bytes):
            content_type = "application/octet-stream" if format_type.upper() == "PARQUET" else "text/plain"
            blob.upload_from_string(data if format_type.upper() == "PARQUET" else data.decode("utf-8"), content_type=content_type)
        else:
            import json
            if format_type.upper() == "CSV":
                import csv
                from io import StringIO
                output = StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    writer.writerows(data)
                blob.upload_from_string(output.getvalue(), content_type="text/csv")
            else:
                json_content = json.dumps(data, default=str)
                blob.upload_from_string(json_content, content_type="application/json")