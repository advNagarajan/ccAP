import csv
import json
import random
import time
import uuid
from io import StringIO
from typing import Any

from app.connectors.base import BaseConnector
from app.core.settings import settings
from app.models.domain.artifact import Artifact
from app.models.domain.raw_data import RawData
from app.services.artifact_service import (
    discover_new_artifacts,
    get_unprocessed_artifacts as fetch_unprocessed_artifacts
)


class AzureBlobConnector(BaseConnector):
    """
    Azure Blob Storage connector implementing BaseConnector.
    Connects to Azure Storage Containers to discover, extract, and write datasets.
    """

    def _get_client(self, connection_details: dict):
        from azure.storage.blob import BlobServiceClient

        conn_str = (
            connection_details.get("connection_string") or
            settings.AZURE_STORAGE_CONNECTION_STRING
        )
        if conn_str:
            return BlobServiceClient.from_connection_string(conn_str)

        account_name = connection_details.get("account_name")
        account_key = connection_details.get("account_key")
        if account_name and account_key:
            account_url = f"https://{account_name}.blob.core.windows.net"
            return BlobServiceClient(account_url=account_url, credential=account_key)

        raise ValueError(
            "Azure Blob connection details missing. Provide 'connection_string' "
            "or set AZURE_STORAGE_CONNECTION_STRING in your environment."
        )

    def _get_container_name(self, connection_details: dict) -> str:
        return (
            connection_details.get("container") or
            connection_details.get("bucket") or
            settings.AZURE_LANDING_CONTAINER or
            "landing"
        )

    def list_artifacts(self, source) -> list[Artifact]:
        connection_details = source.connection_details or {}
        container_name = self._get_container_name(connection_details)
        prefix = connection_details.get("prefix", "")

        client = self._get_client(connection_details)
        container_client = client.get_container_client(container_name)

        artifacts = []
        blobs = container_client.list_blobs(name_starts_with=prefix if prefix else None)

        for blob in blobs:
            if blob.name.endswith("/"):
                continue

            last_modified_str = (
                blob.last_modified.isoformat()
                if hasattr(blob.last_modified, "isoformat")
                else str(blob.last_modified)
            )
            etag_str = str(blob.etag or blob.name)

            artifacts.append(
                Artifact(
                    external_id=f"{blob.name}:{etag_str}",
                    artifact_name=blob.name,
                    last_modified=last_modified_str,
                    metadata={
                        "container": container_name,
                        "object_name": blob.name,
                        "size": blob.size,
                        "etag": etag_str
                    }
                )
            )

        return artifacts

    def get_unprocessed_artifacts(
        self,
        source,
        artifacts: list[Artifact],
        db
    ) -> list[Artifact]:
        discover_new_artifacts(
            source.source_id,
            artifacts,
            db
        )
        return fetch_unprocessed_artifacts(
            source.source_id,
            artifacts,
            db
        )

    def extract_sample(
        self,
        source,
        artifact: Artifact
    ) -> RawData:
        connection_details = source.connection_details or {}
        container_name = (
            artifact.metadata.get("container") or
            self._get_container_name(connection_details)
        )
        object_name = artifact.metadata.get("object_name", artifact.artifact_name)

        client = self._get_client(connection_details)
        blob_client = client.get_blob_client(container=container_name, blob=object_name)

        stream = blob_client.download_blob()
        content = stream.readall().decode("utf-8")
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
        connection_details = source.connection_details or {}
        container_name = (
            artifact.metadata.get("container") or
            self._get_container_name(connection_details)
        )
        object_name = artifact.metadata.get("object_name", artifact.artifact_name)

        client = self._get_client(connection_details)
        blob_client = client.get_blob_client(container=container_name, blob=object_name)

        stream = blob_client.download_blob()
        content = stream.readall().decode("utf-8")
        format_type = object_name.split(".")[-1].upper()

        if sample_ratio is not None:
            from app.parsers.registry import PARSERS

            parser = PARSERS.get(format_type)
            if parser is None:
                raise Exception(f"No parser registered for format: {format_type}")

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
                sampled_records = random.sample(
                    dataset.records, min(len(dataset.records), k)
                )
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
        connection_details = source.connection_details or {}
        container_name = self._get_container_name(connection_details)

        client = self._get_client(connection_details)
        blob_client = client.get_blob_client(container=container_name, blob=object_name)

        try:
            properties = blob_client.get_blob_properties()
        except Exception:
            return None

        last_modified_str = (
            properties.last_modified.isoformat()
            if hasattr(properties.last_modified, "isoformat")
            else str(properties.last_modified)
        )
        etag_str = str(properties.etag or object_name)

        return Artifact(
            external_id=f"{object_name}:{etag_str}",
            artifact_name=object_name,
            last_modified=last_modified_str,
            metadata={
                "container": container_name,
                "object_name": object_name,
                "size": properties.size,
                "etag": etag_str
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
        container_name = self._get_container_name(connection_details)
        prefix = connection_details.get("prefix", "").strip()

        client = self._get_client(connection_details)
        container_client = client.get_container_client(container_name)

        object_name = f"{prefix}/{table_name}" if prefix else table_name

        if write_mode.upper() == "APPEND":
            if "." in table_name:
                base, ext = table_name.rsplit(".", 1)
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
                object_name = f"{prefix}/{base}{suffix}" if prefix else f"{base}{suffix}"
            else:
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                object_name = f"{object_name}{suffix}"

        blob_client = container_client.get_blob_client(object_name)

        if isinstance(data, str):
            blob_client.upload_blob(data, overwrite=True)
        elif isinstance(data, bytes):
            blob_client.upload_blob(data, overwrite=True)
        else:
            if format_type.upper() == "CSV":
                output = StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    writer.writerows(data)
                blob_client.upload_blob(output.getvalue(), overwrite=True)
            else:
                json_content = json.dumps(data, default=str)
                blob_client.upload_blob(json_content, overwrite=True)
