import json
import logging
from google.cloud import bigquery
from google.oauth2 import service_account

from app.connectors.base import BaseConnector
from app.models.domain.artifact import Artifact
from app.models.domain.raw_data import RawData

logger = logging.getLogger("bigquery_connector")


class BigQueryConnector(BaseConnector):

    def _get_client(self, connection_details) -> bigquery.Client:
        project_id = connection_details.get("project_id")
        credentials_dict = connection_details.get("credentials_json")

        if not credentials_dict:
            raise ValueError(
                "Missing 'credentials_json' in connection details. "
                "A user service account is required to connect to the BigQuery instance."
            )
        if not project_id:
            raise ValueError(
                "Missing 'project_id' in connection details. "
                "A GCP project ID is required to connect to the BigQuery instance."
            )

        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return bigquery.Client(
            project=project_id,
            credentials=credentials
        )

    def list_artifacts(
        self,
        source
    ) -> list[Artifact]:
        connection_details = source.connection_details
        dataset_id = connection_details.get("dataset")
        table_name = connection_details.get("table")

        if not dataset_id:
            raise ValueError("Missing 'dataset' in connection details.")
        if not table_name:
            raise ValueError("Missing 'table' in connection details.")

        client = self._get_client(connection_details)
        project_id = client.project
        table_ref = f"{project_id}.{dataset_id}.{table_name}"

        try:
            table = client.get_table(table_ref)
            last_modified_iso = table.modified.isoformat()
            version_suffix = str(int(table.modified.timestamp()))
            external_id = f"{dataset_id}:{table_name}:{version_suffix}"

            return [
                Artifact(
                    external_id=external_id,
                    artifact_name=table_name,
                    last_modified=last_modified_iso,
                    metadata={
                        "dataset": dataset_id,
                        "table": table_name,
                        "last_modified": last_modified_iso,
                        "num_rows": table.num_rows,
                        "etag": external_id
                    }
                )
            ]
        except Exception as e:
            logger.error(f"Failed to fetch BigQuery table metadata for {table_ref}: {e}")
            return []

    def get_unprocessed_artifacts(
        self,
        source,
        artifacts,
        db
    ) -> list[Artifact]:
        from app.services.artifact_service import (
            discover_new_artifacts,
            get_unprocessed_artifacts
        )
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
        dataset_id = artifact.metadata["dataset"]
        table_name = artifact.metadata["table"]

        client = self._get_client(source.connection_details)
        project_id = client.project
        table_ref = f"{project_id}.{dataset_id}.{table_name}"

        query = f"SELECT * FROM `{table_ref}` LIMIT 1000"
        query_job = client.query(query)
        results = query_job.result()

        records = [dict(row) for row in results]
        content = json.dumps(records, default=str)

        connector_metadata = dict(artifact.metadata)
        connector_metadata["sampled_count"] = len(records)

        return RawData(
            content=content,
            format_type="JSON",
            source_type=source.source_type,
            source_name=table_name,
            connector_metadata=connector_metadata
        )

    def extract_full(
        self,
        source,
        artifact: Artifact,
        sample_ratio: float | None = None,
        random_sample: bool = False
    ) -> RawData:
        dataset_id = artifact.metadata["dataset"]
        table_name = artifact.metadata["table"]

        client = self._get_client(source.connection_details)
        project_id = client.project
        table_ref = f"{project_id}.{dataset_id}.{table_name}"

        if sample_ratio is not None:
            num_rows = artifact.metadata.get("num_rows", 10000)
            limit_count = max(1, int(num_rows * sample_ratio))
            if random_sample:
                query = f"SELECT * FROM `{table_ref}` ORDER BY RAND() LIMIT {limit_count}"
            else:
                query = f"SELECT * FROM `{table_ref}` LIMIT {limit_count}"
        else:
            query = f"SELECT * FROM `{table_ref}`"

        query_job = client.query(query)
        results = query_job.result()

        records = [dict(row) for row in results]
        content = json.dumps(records, default=str)

        return RawData(
            content=content,
            format_type="JSON",
            source_type=source.source_type,
            source_name=table_name,
            connector_metadata=artifact.metadata
        )

    def get_artifact(
        self,
        source,
        artifact_external_id: str
    ) -> Artifact | None:
        if ":" not in artifact_external_id:
            return None

        parts = artifact_external_id.split(":")
        dataset_id = parts[0]
        table_name = parts[1]

        connection_details = source.connection_details
        client = self._get_client(connection_details)
        project_id = client.project
        table_ref = f"{project_id}.{dataset_id}.{table_name}"

        try:
            table = client.get_table(table_ref)
            last_modified_iso = table.modified.isoformat()
            version_suffix = str(int(table.modified.timestamp()))
            external_id = f"{dataset_id}:{table_name}:{version_suffix}"

            return Artifact(
                external_id=external_id,
                artifact_name=table_name,
                last_modified=last_modified_iso,
                metadata={
                    "dataset": dataset_id,
                    "table": table_name,
                    "last_modified": last_modified_iso,
                    "num_rows": table.num_rows,
                    "etag": external_id
                }
            )
        except Exception as e:
            logger.error(f"Failed to fetch BigQuery table metadata for get_artifact on {table_ref}: {e}")
            return None
