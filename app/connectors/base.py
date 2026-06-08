from abc import ABC, abstractmethod

from app.models.artifact import Artifact
from app.models.raw_data import RawData


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
        artifact: Artifact
    ) -> RawData:
        pass
    
    @abstractmethod
    def get_artifact(
        self,
        source,
        artifact_external_id: str
    ) -> Artifact | None:
        pass