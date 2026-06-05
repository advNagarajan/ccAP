from abc import ABC, abstractmethod

from app.models.raw_data import RawData


class BaseConnector(ABC):

    @abstractmethod
    def extract(self, source) -> RawData:
        pass