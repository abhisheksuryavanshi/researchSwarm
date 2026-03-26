from __future__ import annotations

from typing import Protocol, runtime_checkable

import structlog

from registry.config import EmbeddingProviderType, Settings

logger = structlog.get_logger()

VECTOR_DIMENSION = 768


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class LocalEmbeddingProvider:
    """sentence-transformers/all-MiniLM-L6-v2 — 384 dims, zero-padded to 768."""

    def __init__(self) -> None:
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")

    async def embed(self, text: str) -> list[float]:
        self._load_model()
        vec = self._model.encode(text).tolist()
        # Zero-pad from 384 to 768
        return vec + [0.0] * (VECTOR_DIMENSION - len(vec))


class GoogleEmbeddingProvider:
    """Google GenAI text-embedding-004 — 768 dims."""

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        result = self._client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return list(result.embeddings[0].values)


class OpenAIEmbeddingProvider:
    """OpenAI text-embedding-3-small — truncated to 768 dims."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1") -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def embed(self, text: str) -> list[float]:
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        vec = response.data[0].embedding
        return vec[:VECTOR_DIMENSION]


def get_embedding_provider(s: Settings) -> EmbeddingProvider:
    if s.embedding_provider == EmbeddingProviderType.GOOGLE:
        if not s.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for google embedding provider")
        return GoogleEmbeddingProvider(api_key=s.google_api_key)
    elif s.embedding_provider == EmbeddingProviderType.OPENAI:
        if not s.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for openai embedding provider")
        return OpenAIEmbeddingProvider(api_key=s.openai_api_key, base_url=s.openai_api_base)
    else:
        return LocalEmbeddingProvider()
