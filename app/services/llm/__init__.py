from app.services.llm.base import BaseEmbeddingProvider, BaseLLMProvider
from app.services.llm.vertex_provider import VertexEmbeddingProvider, VertexLLMProvider

_embedding_instance = None
_llm_instance = None

def get_embedding_provider() -> BaseEmbeddingProvider:
    global _embedding_instance
    if _embedding_instance is None:
        _embedding_instance = VertexEmbeddingProvider()
    return _embedding_instance


def get_llm_provider() -> BaseLLMProvider:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = VertexLLMProvider()
    return _llm_instance
