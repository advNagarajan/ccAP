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


class S3Connector(BaseConnector):
    """
    AWS S3 Connector implementing BaseConnector.
    Connects to Amazon S3 buckets to discover, extract, and write datasets.
    """

    def _get_client(self, connection_details: dict):
        import boto3

        region = (
            connection_details.get("region") or
            connection_details.get("aws_region") or
            settings.AWS_REGION or
            "us-east-1"
        )
        kwargs = {"region_name": region}

        access_key = (
            connection_details.get("aws_access_key_id") or
            settings.AWS_ACCESS_KEY_ID
        )
        secret_key = (
            connection_details.get("aws_secret_access_key") or
            settings.AWS_SECRET_ACCESS_KEY
        )

        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key

        return boto3.client("s3", **kwargs)

    def _get_bucket_name(self, connection_details: dict) -> str:
        return (
            connection_details.get("bucket") or
            connection_details.get("bucket_name") or
            settings.AWS_S3_LANDING_BUCKET or
            "dataset-platform-landing"
        )

    def list_artifacts(self, source) -> list[Artifact]:
        connection_details = source.connection_details or {}
        bucket_name = self._get_bucket_name(connection_details)
        prefix = connection_details.get("prefix", "")

        client = self._get_client(connection_details)
        kwargs = {"Bucket": bucket_name}
        if prefix:
            kwargs["Prefix"] = prefix

        artifacts = []
        paginator = client.get_paginator("list_objects_v2")

        for page in paginator.paginate(**kwargs):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith("/"):
                    continue

                last_modified_str = item["LastModified"].isoformat()
                etag_str = item["ETag"].strip('"')

                artifacts.append(
                    Artifact(
                        external_id=f"{key}:{etag_str}",
                        artifact_name=key,
                        last_modified=last_modified_str,
                        metadata={
                            "bucket": bucket_name,
                            "object_name": key,
                            "size": item["Size"],
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
        bucket_name = (
            artifact.metadata.get("bucket") or
            self._get_bucket_name(connection_details)
        )
        object_name = artifact.metadata.get("object_name", artifact.artifact_name)

        client = self._get_client(connection_details)
        response = client.get_object(Bucket=bucket_name, Key=object_name)
        content = response["Body"].read().decode("utf-8")
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
        bucket_name = (
            artifact.metadata.get("bucket") or
            self._get_bucket_name(connection_details)
        )
        object_name = artifact.metadata.get("object_name", artifact.artifact_name)

        client = self._get_client(connection_details)
        response = client.get_object(Bucket=bucket_name, Key=object_name)
        content = response["Body"].read().decode("utf-8")
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
        bucket_name = self._get_bucket_name(connection_details)

        client = self._get_client(connection_details)
        try:
            response = client.head_object(Bucket=bucket_name, Key=object_name)
        except Exception:
            return None

        last_modified_str = response["LastModified"].isoformat()
        etag_str = response["ETag"].strip('"')

        return Artifact(
            external_id=f"{object_name}:{etag_str}",
            artifact_name=object_name,
            last_modified=last_modified_str,
            metadata={
                "bucket": bucket_name,
                "object_name": object_name,
                "size": response["ContentLength"],
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
        bucket_name = self._get_bucket_name(connection_details)
        prefix = connection_details.get("prefix", "").strip()

        client = self._get_client(connection_details)
        object_name = f"{prefix}/{table_name}" if prefix else table_name

        if write_mode.upper() == "APPEND":
            if "." in table_name:
                base, ext = table_name.rsplit(".", 1)
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
                object_name = f"{prefix}/{base}{suffix}" if prefix else f"{base}{suffix}"
            else:
                suffix = f"_part_{int(time.time())}_{uuid.uuid4().hex[:6]}"
                object_name = f"{object_name}{suffix}"

        content_type = "text/plain"
        if isinstance(data, str):
            content_type = "text/csv" if format_type.upper() == "CSV" else "application/json"
            body = data.encode("utf-8")
        elif isinstance(data, bytes):
            content_type = "application/octet-stream" if format_type.upper() == "PARQUET" else "text/plain"
            body = data
        else:
            if format_type.upper() == "CSV":
                content_type = "text/csv"
                output = StringIO()
                if data:
                    writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                    writer.writeheader()
                    writer.writerows(data)
                body = output.getvalue().encode("utf-8")
            else:
                content_type = "application/json"
                body = json.dumps(data, default=str).encode("utf-8")

        client.put_object(
            Bucket=bucket_name,
            Key=object_name,
            Body=body,
            ContentType=content_type
        )
