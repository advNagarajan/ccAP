from abc import ABC, abstractmethod

from app.models.domain.artifact import Artifact
from app.models.domain.raw_data import RawData


class BaseConnector(ABC):

    @abstractmethod
    def list_artifacts(
        self,
        source
    ) -> list[Artifact]:
        pass

    @abstractmethod
    def get_unprocessed_artifacts(
        self,
        source,
        artifacts,
        db
    ) -> list[Artifact]:
        pass

    @abstractmethod
    def extract_sample(
        self,
        source,
        artifact: Artifact
    ) -> RawData:
        pass

    @abstractmethod
    def extract_full(
        self,
        source,
        artifact: Artifact,
        sample_ratio: float | None = None,
        random_sample: bool = False
    ) -> RawData:
        pass
    
    @abstractmethod
    def get_artifact(
        self,
        source,
        artifact_external_id: str
    ) -> Artifact | None:
        pass

    @abstractmethod
    def write_data(
        self,
        connection_details: dict,
        data: list[dict] | str | bytes,
        format_type: str,
        table_name: str,
        write_mode: str = "APPEND",
        key_columns: list[str] | None = None
    ) -> None:
        pass