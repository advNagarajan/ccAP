from abc import ABC, abstractmethod

from app.models.dataset import Dataset
from app.models.raw_data import RawData


class BaseParser(ABC):

    @abstractmethod
    def parse(self, raw_data: RawData) -> Dataset:
        pass