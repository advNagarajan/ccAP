from abc import ABC, abstractmethod

class BaseEmbeddingProvider(ABC):

    @abstractmethod
    async def get_embedding(self, text: str) -> list[float]:
        """
        Retrieves dense vector representation for the input text.
        """
        pass


class BaseLLMProvider(ABC):

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        response_schema: type | None = None
    ) -> str:
        """
        Generates text or structured response from the generative model.
        """
        pass
