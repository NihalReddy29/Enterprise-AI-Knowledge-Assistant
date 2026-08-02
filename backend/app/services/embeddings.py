"""Embedding generation service with multiple providers."""

from __future__ import annotations

import hashlib
import logging
import math
from abc import ABC, abstractmethod
from typing import Sequence

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingProvider(ABC):
    """Interface for embedding backends."""

    @abstractmethod
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed a batch of documents."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identifier."""


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embeddings for tests and offline development."""

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension or settings.embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "fake"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        values = [0.0] * self._dimension
        normalized = "".join(ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in text)
        tokens = [t for t in normalized.split() if t]
        if not tokens:
            digest = hashlib.sha256(b"empty").digest()
            return _l2_normalize([(b / 255.0) * 2.0 - 1.0 for b in digest[: self._dimension]])

        for token in tokens:
            # Hash whole token into several dimensions
            for salt in (b"t0", b"t1", b"t2", b"t3"):
                digest = hashlib.md5(token.encode("utf-8") + salt).digest()
                idx = int.from_bytes(digest[:4], "big") % self._dimension
                values[idx] += 1.0

            # Character trigrams for partial lexical overlap
            padded = f"#{token}#"
            for i in range(len(padded) - 2):
                gram = padded[i : i + 3]
                digest = hashlib.md5(gram.encode("utf-8")).digest()
                idx = int.from_bytes(digest[:4], "big") % self._dimension
                values[idx] += 0.35

        return _l2_normalize(values)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI / OpenAI-compatible embeddings API."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")

        from openai import OpenAI

        kwargs: dict = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        self.client = OpenAI(**kwargs)
        self.model = settings.openai_embedding_model
        self._dimension = settings.embedding_dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "openai"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(model=self.model, input=list(texts))
        vectors = [item.embedding for item in response.data]
        if vectors:
            self._dimension = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embeddings."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")

        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        self.model = settings.gemini_embedding_model
        self._dimension = settings.embedding_dimension
        self._genai = genai

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "gemini"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            result = self._genai.embed_content(
                model=self.model,
                content=text,
                task_type="retrieval_document",
                output_dimensionality=settings.embedding_dimension,
            )
            vector = result["embedding"]
            vectors.append(vector)
            self._dimension = len(vector)
        return vectors

    def embed_query(self, text: str) -> list[float]:
        result = self._genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_query",
            output_dimensionality=settings.embedding_dimension,
        )
        vector = result["embedding"]
        self._dimension = len(vector)
        return vector


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """Local HuggingFace sentence-transformers embeddings."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(settings.huggingface_embedding_model)
        self._dimension = self.model.get_sentence_embedding_dimension()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return "huggingface"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(list(texts), normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class EmbeddingService:
    """High-level embedding service used by indexing and search."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self.provider = provider or create_embedding_provider()

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    @property
    def provider_name(self) -> str:
        return self.provider.provider_name

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Convert text chunks into vectors."""
        if not texts:
            return []
        return self.provider.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        """Convert a query into a vector."""
        return self.provider.embed_query(text)


def create_embedding_provider(provider_name: str | None = None) -> EmbeddingProvider:
    """Factory for configured embedding provider."""
    name = (provider_name or settings.default_embedding_provider).lower()

    if name == "fake":
        return FakeEmbeddingProvider()
    if name == "openai":
        return OpenAIEmbeddingProvider()
    if name == "gemini":
        return GeminiEmbeddingProvider()
    if name in ("huggingface", "hf"):
        return HuggingFaceEmbeddingProvider()

    raise ValueError(
        f"Unknown embedding provider '{name}'. "
        "Supported: openai, gemini, huggingface, fake"
    )


def get_embedding_service() -> EmbeddingService:
    """Return configured embedding service."""
    return EmbeddingService()


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]
