import asyncio
import logging
from google import genai
from google.auth import exceptions as auth_exceptions
from app.core.settings import settings
from app.services.llm.base import BaseEmbeddingProvider, BaseLLMProvider

logger = logging.getLogger("llm_providers")


class VertexEmbeddingProvider(BaseEmbeddingProvider):

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.GCP_LOCATION
        self.model = settings.VERTEX_EMBEDDING_MODEL or "text-embedding-004"
        logger.info(f"Initializing VertexEmbeddingProvider on model={self.model} location={self.location}")
        self._init_client()

    def _init_client(self):
        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location
        )

    async def get_embedding(self, text: str) -> list[float]:
        if not self.model:
            logger.warning("No VERTEX_EMBEDDING_MODEL configured. Returning mock embedding.")
            return [0.0] * 768
            
        try:
            response = await asyncio.to_thread(
                self.client.models.embed_content,
                model=self.model,
                contents=text
            )
            if not response or not response.embeddings:
                raise ValueError("No embeddings returned from Vertex AI.")
            return response.embeddings[0].values
        except Exception as e:
            err_str = str(e).lower()
            if isinstance(e, auth_exceptions.RefreshError) or any(k in err_str for k in ["refresherror", "refresh token", "credentials", "googleauth", "unauthorized", "authenticated"]):
                logger.warning(f"Credential/auth error in VertexEmbeddingProvider: {e}. Re-initializing client and retrying...")
                try:
                    self._init_client()
                    response = await asyncio.to_thread(
                        self.client.models.embed_content,
                        model=self.model,
                        contents=text
                    )
                    if not response or not response.embeddings:
                        raise ValueError("No embeddings returned from Vertex AI after client re-initialization.")
                    return response.embeddings[0].values
                except Exception as retry_err:
                    logger.error(f"Failed to fetch embedding on retry after client re-initialization: {retry_err}")
                    raise retry_err
            else:
                logger.error(f"Failed to fetch embedding from Vertex: {e}")
                raise


class VertexLLMProvider(BaseLLMProvider):

    def __init__(self):
        self.project_id = settings.GCP_PROJECT_ID
        self.location = settings.GCP_LOCATION
        self.model = settings.VERTEX_GENERATIVE_MODEL or "gemini-2.5-flash"
        logger.info(f"Initializing VertexLLMProvider on model={self.model} location={self.location}")
        self._init_client()

    def _init_client(self):
        self.client = genai.Client(
            vertexai=True,
            project=self.project_id,
            location=self.location
        )

    async def generate_response(
        self,
        prompt: str,
        response_schema: type | None = None
    ) -> str:
        from google.genai import types

        config = None
        if response_schema is not None:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema
            )

        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
                config=config
            )
            return response.text
        except Exception as e:
            err_str = str(e).lower()
            if isinstance(e, auth_exceptions.RefreshError) or any(k in err_str for k in ["refresherror", "refresh token", "credentials", "googleauth", "unauthorized", "authenticated"]):
                logger.warning(f"Credential/auth error in VertexLLMProvider: {e}. Re-initializing client and retrying...")
                try:
                    self._init_client()
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model,
                        contents=prompt,
                        config=config
                    )
                    return response.text
                except Exception as retry_err:
                    logger.error(f"Failed to generate response on retry after client re-initialization: {retry_err}")
                    raise retry_err
            else:
                logger.error(f"Failed to generate response from Vertex: {e}")
                raise
