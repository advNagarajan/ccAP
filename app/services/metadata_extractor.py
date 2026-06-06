from app.models.dataset import Dataset
from app.models.metadata import DatasetMetadata


class MetadataExtractor:

    def extract(
        self,
        dataset: Dataset,
        connector_metadata: dict
    ) -> DatasetMetadata:

        pass