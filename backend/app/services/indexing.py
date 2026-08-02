"""Document indexing: chunk → embed → store in vector database."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.chunking import ChunkingService, DocumentChunk, get_chunking_service
from app.services.document_processor import ExtractionResult
from app.services.embeddings import EmbeddingService, get_embedding_service
from app.services.vector_store import SearchResult, VectorStore, get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class IndexingResult:
    """Result of indexing a document."""

    document_id: int
    chunk_count: int
    embedding_provider: str
    vector_store: str


class IndexingService:
    """Orchestrates chunking, embedding, and vector upsert."""

    def __init__(
        self,
        chunking: ChunkingService | None = None,
        embeddings: EmbeddingService | None = None,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.chunking = chunking or get_chunking_service()
        self.embeddings = embeddings or get_embedding_service()
        self.vector_store = vector_store or get_vector_store()

    def index_document(
        self,
        result: ExtractionResult,
        document_id: int,
        filename: str,
        owner_id: int,
    ) -> IndexingResult:
        """Chunk, embed, and upsert document vectors."""
        chunks = self.chunking.chunk_extraction(
            result=result,
            document_id=document_id,
            filename=filename,
            owner_id=owner_id,
        )
        if not chunks:
            raise ValueError("No chunks produced for indexing")

        # Replace existing vectors for this document
        self.vector_store.delete_by_document(document_id)
        self.vector_store.ensure_collection(self.embeddings.dimension)

        texts = [chunk.text for chunk in chunks]
        vectors = self.embeddings.embed_texts(texts)
        if len(vectors) != len(chunks):
            raise RuntimeError("Embedding count mismatch")

        ids = [self._chunk_id(chunk) for chunk in chunks]
        payloads = [chunk.to_metadata() for chunk in chunks]
        self.vector_store.upsert(ids=ids, vectors=vectors, payloads=payloads)

        logger.info(
            "Indexed document %d: %d chunks via %s → %s",
            document_id,
            len(chunks),
            self.embeddings.provider_name,
            type(self.vector_store).__name__,
        )

        return IndexingResult(
            document_id=document_id,
            chunk_count=len(chunks),
            embedding_provider=self.embeddings.provider_name,
            vector_store=type(self.vector_store).__name__,
        )

    def search(
        self,
        query: str,
        top_k: int = 5,
        owner_id: int | None = None,
        document_ids: list[int] | None = None,
    ) -> list[SearchResult]:
        """Embed query and retrieve similar chunks."""
        query_vector = self.embeddings.embed_query(query)
        filters: dict = {}
        if owner_id is not None:
            filters["owner_id"] = owner_id
        if document_ids:
            filters["document_ids"] = document_ids

        return self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
            filters=filters or None,
        )

    def delete_document(self, document_id: int) -> None:
        """Remove document vectors from the store."""
        self.vector_store.delete_by_document(document_id)

    @staticmethod
    def _chunk_id(chunk: DocumentChunk) -> str:
        return f"doc-{chunk.document_id}-chunk-{chunk.chunk_index}"


def get_indexing_service() -> IndexingService:
    """Return configured indexing service."""
    return IndexingService()
