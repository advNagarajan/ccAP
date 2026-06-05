from google.cloud import storage

from app.connectors.base import BaseConnector
from app.models.raw_data import RawData


class GCSConnector(BaseConnector):

    def extract(self, source) -> RawData:
        connection_details = source.connection_details

        bucket_name = connection_details["bucket"]
        object_path = connection_details["object_path"]

        client = storage.Client()

        bucket = client.bucket(bucket_name)

        blob = bucket.blob(object_path)

        content = blob.download_as_text()

        format_type = object_path.split(".")[-1].upper()

        return RawData(
            content=content,
            format_type=format_type,
            source_name=object_path
        )