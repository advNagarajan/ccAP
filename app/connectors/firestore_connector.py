import json
import random
from datetime import datetime
from sqlalchemy import select
from google.cloud import firestore
from google.oauth2 import service_account

from app.db.database import SessionLocal
from app.models.db.artifact_record import ArtifactRecord
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

    def list_artifacts(self, source) -> list[Artifact]:
        connection_details = source.connection_details
        collection_name = connection_details["collection"]

        client = self._get_client(connection_details)
        docs = client.collection(collection_name).select([]).stream()

        max_update_time = None
        for doc in docs:
            update_time = doc.update_time
            if max_update_time is None or update_time > max_update_time:
                max_update_time = update_time

        if max_update_time is None:
            return []

        try:
            version_suffix = f"{max_update_time.timestamp_pb().seconds}_{max_update_time.timestamp_pb().nanoseconds}"
        except AttributeError:
            version_suffix = f"{int(max_update_time.timestamp())}"

        external_id = f"{collection_name}:{version_suffix}"
        max_update_time_iso = max_update_time.isoformat()

        return [
            Artifact(
                external_id=external_id,
                artifact_name=collection_name,
                last_modified=max_update_time_iso,
                metadata={
                    "collection": collection_name,
                    "object_name": collection_name,
                    "update_time": max_update_time_iso,
                    "etag": f"{collection_name}:{version_suffix}"
                }
            )
        ]

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

        client = self._get_client(source.connection_details)
        
        # 1. Fetch document references only (metadata scan)
        doc_snapshots = list(client.collection(collection_name).select([]).stream())
        
        # 2. Randomly sample up to 1000 documents
        sampled_snapshots = random.sample(doc_snapshots, min(len(doc_snapshots), 1000))
        sampled_refs = [snap.reference for snap in sampled_snapshots]
        
        # 3. Batch fetch the sampled documents
        docs = client.get_all(sampled_refs) if sampled_refs else []

        records = []
        for doc in docs:
            if doc.exists:
                records.append(doc.to_dict())

        content = json.dumps(records, default=str)

        connector_metadata = dict(artifact.metadata)
        connector_metadata["sampled_count"] = len(records)

        return RawData(
            content=content,
            format_type="JSON",
            source_type=source.source_type,
            source_name=collection_name,
            connector_metadata=connector_metadata
        )

    def extract_full(
        self,
        source,
        artifact: Artifact,
        sample_ratio: float | None = None,
        random_sample: bool = False
    ) -> RawData:
        collection_name = artifact.metadata["collection"]
        previous_update_time = self._get_previous_update_time(source.source_id)

        client = self._get_client(source.connection_details)

        if sample_ratio is not None:
            # 1. Fetch document references only
            doc_snapshots = list(client.collection(collection_name).select([]).stream())
            k = max(1, int(len(doc_snapshots) * sample_ratio))
            
            # 2. Sample references
            if random_sample:
                sampled_snapshots = random.sample(doc_snapshots, min(len(doc_snapshots), k))
            else:
                sampled_snapshots = doc_snapshots[:k]
                
            sampled_refs = [snap.reference for snap in sampled_snapshots]
            
            # 3. Batch fetch the sampled documents
            docs = client.get_all(sampled_refs) if sampled_refs else []
        else:
            docs = client.collection(collection_name).stream()

        records = []
        for doc in docs:
            # Note: doc might be from get_all (so check if it exists) or stream
            if hasattr(doc, "exists") and not doc.exists:
                continue
            if previous_update_time is None or doc.update_time > previous_update_time:
                records.append(doc.to_dict())

        content = json.dumps(records, default=str)

        return RawData(
            content=content,
            format_type="JSON",
            source_type=source.source_type,
            source_name=collection_name,
            connector_metadata=artifact.metadata
        )

    def get_artifact(self, source, artifact_external_id: str) -> Artifact | None:
        if ":" not in artifact_external_id:
            return None
            
        collection_name = artifact_external_id.split(":")[0]
        connection_details = source.connection_details

        client = self._get_client(connection_details)
        docs = client.collection(collection_name).select([]).stream()

        max_update_time = None
        for doc in docs:
            update_time = doc.update_time
            if max_update_time is None or update_time > max_update_time:
                max_update_time = update_time

        if max_update_time is None:
            return None

        try:
            version_suffix = f"{max_update_time.timestamp_pb().seconds}_{max_update_time.timestamp_pb().nanoseconds}"
        except AttributeError:
            version_suffix = f"{int(max_update_time.timestamp())}"

        max_update_time_iso = max_update_time.isoformat()

        return Artifact(
            external_id=f"{collection_name}:{version_suffix}",
            artifact_name=collection_name,
            last_modified=max_update_time_iso,
            metadata={
                "collection": collection_name,
                "object_name": collection_name,
                "update_time": max_update_time_iso,
                "etag": f"{collection_name}:{version_suffix}"
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
        import csv
        from io import StringIO

        collection_name = table_name or connection_details.get("collection")
        if not collection_name:
            raise ValueError("Missing collection name. Provide a table_name or collection in connection details.")

        write_mode_upper = write_mode.upper()
        if write_mode_upper not in ["APPEND", "OVERWRITE", "UPSERT"]:
            raise ValueError(f"Unsupported write mode: {write_mode}")

        client = self._get_client(connection_details)
        collection_ref = client.collection(collection_name)

        # Parse data into list of dicts
        records = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = [data]
        elif isinstance(data, (str, bytes)):
            if isinstance(data, bytes):
                content = data.decode("utf-8")
            else:
                content = data

            format_upper = format_type.upper()
            if format_upper == "JSON":
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        records = parsed
                    elif isinstance(parsed, dict):
                        records = [parsed]
                    else:
                        raise ValueError("Parsed JSON is not a list or dictionary.")
                except Exception as e:
                    raise ValueError(f"Failed to parse JSON data: {e}")
            elif format_upper == "CSV":
                try:
                    reader = csv.DictReader(StringIO(content))
                    records = list(reader)
                except Exception as e:
                    raise ValueError(f"Failed to parse CSV data: {e}")
            else:
                raise ValueError(f"Unsupported format type: {format_type}")
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        # Handle OVERWRITE mode: Delete all existing documents in the collection first
        if write_mode_upper == "OVERWRITE":
            docs = collection_ref.select([]).stream()
            batch = client.batch()
            count = 0
            for doc in docs:
                batch.delete(doc.reference)
                count += 1
                if count >= 500:
                    batch.commit()
                    batch = client.batch()
                    count = 0
            if count > 0:
                batch.commit()

        # Write/Update documents using Batch Writer
        batch = client.batch()
        count = 0
        for doc in records:
            if not isinstance(doc, dict):
                raise ValueError("Record data must be a dictionary/document object.")

            doc_id = None
            if key_columns:
                doc_id = "_".join(str(doc.get(k)) for k in key_columns if doc.get(k) is not None)
            else:
                for candidate in ["id", "_id"]:
                    if candidate in doc and doc[candidate] is not None:
                        doc_id = str(doc[candidate])
                        break

            if doc_id:
                doc_ref = collection_ref.document(doc_id)
            else:
                if write_mode_upper == "UPSERT":
                    raise ValueError("UPSERT mode requires key_columns or an 'id'/'_id' field in the document to determine the document ID.")
                doc_ref = collection_ref.document()

            if write_mode_upper == "UPSERT":
                batch.set(doc_ref, doc, merge=True)
            else:
                batch.set(doc_ref, doc)

            count += 1
            if count >= 500:
                batch.commit()
                batch = client.batch()
                count = 0
        if count > 0:
            batch.commit()
