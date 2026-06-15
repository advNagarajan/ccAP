from abc import ABC, abstractmethod

from app.models.domain.dataset import Dataset
from app.models.domain.raw_data import RawData


class BaseParser(ABC):

    @abstractmethod
    def parse(self, raw_data: RawData) -> Dataset:
        pass