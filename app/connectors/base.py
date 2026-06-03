from abc import ABC, abstractmethod


class BaseConnector(ABC):

    @abstractmethod
    def extract(self, source):
        pass