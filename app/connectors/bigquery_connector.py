import json
import logging
from datetime import datetime
from google.cloud import bigquery
from google.oauth2 import service_account
from sqlalchemy import select

from app.db.database import SessionLocal
from app.models.db.artifact_record import ArtifactRecord
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

    def _get_previous_update_time(self, source_id) -> datetime | None:
        db = SessionLocal()
        try:
            last_record = db.execute(
                select(ArtifactRecord)
                .where(ArtifactRecord.source_id == source_id)
                .where(ArtifactRecord.status == "PROCESSED")
                .order_by(ArtifactRecord.processed_at.desc())
            ).scalars().first()

            if last_record and "update_time" in last_record.artifact_metadata:
                try:
                    return datetime.fromisoformat(last_record.artifact_metadata["update_time"])
                except Exception:
                    pass
            return None
        finally:
            db.close()

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
                        "update_time": last_modified_iso,
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

        # Get previous update time
        previous_update_time = self._get_previous_update_time(source.source_id)

        # Determine if we should query incrementally
        incremental_column = source.connection_details.get("incremental_column")
        
        # If not specified, look up table schema to find common timestamp column names
        if not incremental_column:
            try:
                table = client.get_table(table_ref)
                schema_cols = [field.name.lower() for field in table.schema]
                for candidate in ["updated_at", "modified_at", "update_time", "timestamp", "created_at"]:
                    if candidate in schema_cols:
                        incremental_column = next(field.name for field in table.schema if field.name.lower() == candidate)
                        break
            except Exception as e:
                logger.warning(f"Failed to inspect schema for incremental columns: {e}")

        # Build SQL query with limit or TABLESAMPLE if sample_ratio is provided
        where_clause = ""
        if previous_update_time and incremental_column:
            # Format timestamp for BigQuery SQL
            timestamp_str = previous_update_time.strftime("%Y-%m-%d %H:%M:%S.%f UTC")
            where_clause = f" WHERE `{incremental_column}` > '{timestamp_str}'"

        if sample_ratio is not None:
            num_rows = artifact.metadata.get("num_rows", 10000)
            limit_count = max(1, int(num_rows * sample_ratio))
            if random_sample:
                query = f"SELECT * FROM `{table_ref}`{where_clause} ORDER BY RAND() LIMIT {limit_count}"
            else:
                query = f"SELECT * FROM `{table_ref}`{where_clause} LIMIT {limit_count}"
        else:
            query = f"SELECT * FROM `{table_ref}`{where_clause}"

        logger.info(f"BigQuery extract query: {query}")
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
                    "update_time": last_modified_iso,
                    "num_rows": table.num_rows,
                    "etag": external_id
                }
            )
        except Exception as e:
            logger.error(f"Failed to fetch BigQuery table metadata for get_artifact on {table_ref}: {e}")
            return None

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
        dataset_id = connection_details.get("dataset")

        if not dataset_id:
            raise ValueError("Missing 'dataset' in connection details.")

        table_ref = f"{client.project}.{dataset_id}.{table_name}"
        write_mode_upper = write_mode.upper()

        if write_mode_upper == "UPSERT":
            if not key_columns:
                raise ValueError("key_columns is required for UPSERT mode")

            import uuid
            staging_table_name = f"{table_name}_staging_{uuid.uuid4().hex[:8]}"
            staging_ref = f"{client.project}.{dataset_id}.{staging_table_name}"

            # Create an empty staging table with the same schema as the target
            client.query(f"CREATE TABLE `{staging_ref}` LIKE `{table_ref}`").result()

            try:
                # Load incoming data into the staging table (always APPEND into staging)
                self.write_data(
                    connection_details=connection_details,
                    data=data,
                    format_type=format_type,
                    table_name=staging_table_name,
                    write_mode="APPEND"
                )

                # Get the schema columns to write the MERGE statement
                target_table = client.get_table(table_ref)
                columns = [field.name for field in target_table.schema]

                on_clause = " AND ".join(f"T.`{k}` = S.`{k}`" for k in key_columns)
                non_key_cols = [c for c in columns if c not in key_columns]
                
                if non_key_cols:
                    update_clause = "WHEN MATCHED THEN UPDATE SET " + ", ".join(f"T.`{c}` = S.`{c}`" for c in non_key_cols)
                else:
                    update_clause = ""

                insert_cols = ", ".join(f"`{c}`" for c in columns)
                insert_vals = ", ".join(f"S.`{c}`" for c in columns)
                insert_clause = f"WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})"

                merge_query = f"""
                MERGE `{table_ref}` T
                USING `{staging_ref}` S
                ON {on_clause}
                {update_clause}
                {insert_clause}
                """
                client.query(merge_query).result()

            finally:
                client.delete_table(staging_ref, not_found_ok=True)
            return

        # Handle APPEND or OVERWRITE
        write_disposition = (
            bigquery.WriteDisposition.WRITE_APPEND
            if write_mode_upper == "APPEND"
            else bigquery.WriteDisposition.WRITE_TRUNCATE
        )

        format_upper = format_type.upper()
        if format_upper == "JSON":
            source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON
        elif format_upper == "CSV":
            source_format = bigquery.SourceFormat.CSV
        elif format_upper == "PARQUET":
            source_format = bigquery.SourceFormat.PARQUET
        else:
            raise ValueError(f"Unsupported format type: {format_type}")

        # Check if data represents GCS URIs
        is_gcs_uri = False
        if isinstance(data, str) and data.startswith("gs://"):
            is_gcs_uri = True
            uris = [data]
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], str) and data[0].startswith("gs://"):
            is_gcs_uri = True
            uris = data
        elif isinstance(data, str) and data.strip().startswith("["):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], str) and parsed[0].startswith("gs://"):
                    is_gcs_uri = True
                    uris = parsed
            except Exception:
                pass

        job_config = bigquery.LoadJobConfig(
            source_format=source_format,
            write_disposition=write_disposition,
            create_disposition=bigquery.CreateDisposition.CREATE_NEVER
        )
        if format_upper == "CSV":
            job_config.skip_leading_rows = 1

        if is_gcs_uri:
            load_job = client.load_table_from_uri(uris, table_ref, job_config=job_config)
            load_job.result()
        else:
            import io
            if format_upper == "JSON":
                if isinstance(data, str):
                    data = data.strip()
                    if data.startswith("["):
                        records = json.loads(data)
                        ndjson_str = "\n".join(json.dumps(r, default=str) for r in records)
                    else:
                        ndjson_str = data
                    data_file = io.BytesIO(ndjson_str.encode("utf-8"))
                elif isinstance(data, bytes):
                    decoded = data.decode("utf-8").strip()
                    if decoded.startswith("["):
                        records = json.loads(decoded)
                        ndjson_str = "\n".join(json.dumps(r, default=str) for r in records)
                    else:
                        ndjson_str = decoded
                    data_file = io.BytesIO(ndjson_str.encode("utf-8"))
                else:
                    ndjson_str = "\n".join(json.dumps(r, default=str) for r in data)
                    data_file = io.BytesIO(ndjson_str.encode("utf-8"))
            elif format_upper == "CSV":
                if isinstance(data, str):
                    data_file = io.BytesIO(data.encode("utf-8"))
                elif isinstance(data, bytes):
                    data_file = io.BytesIO(data)
                else:
                    import csv
                    output = io.StringIO()
                    if data:
                        writer = csv.DictWriter(output, fieldnames=list(data[0].keys()))
                        writer.writeheader()
                        writer.writerows(data)
                    data_file = io.BytesIO(output.getvalue().encode("utf-8"))
            elif format_upper == "PARQUET":
                if isinstance(data, bytes):
                    data_file = io.BytesIO(data)
                else:
                    raise ValueError("Parquet data must be provided as bytes")
            else:
                raise ValueError(f"Unhandled format: {format_type}")

            load_job = client.load_table_from_file(data_file, table_ref, job_config=job_config)
            load_job.result()
