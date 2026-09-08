"""Vector store abstraction supporting Qdrant, Chroma, Pinecone, and in-memory."""

from __future__ import annotations

import logging
import math
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SearchResult:
    """A single semantic search hit."""

    text: str
    document_id: int
    filename: str | None
    page_number: int | None
    section: str | None
    similarity_score: float
    chunk_index: int | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "document": self.filename,
            "document_id": self.document_id,
            "page_number": self.page_number,
            "section": self.section,
            "similarity_score": self.similarity_score,
            "chunk_index": self.chunk_index,
        }


class VectorStore(ABC):
    """Interface for vector similarity search backends."""

    @abstractmethod
    def ensure_collection(self, dimension: int) -> None:
        """Create collection/index if it does not exist."""

    @abstractmethod
    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        """Insert or update vectors with metadata payloads."""

    @abstractmethod
    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Return top-K similar chunks."""

    @abstractmethod
    def delete_by_document(self, document_id: int) -> None:
        """Remove all vectors for a document."""

    @abstractmethod
    def count(self) -> int:
        """Return approximate vector count."""


class InMemoryVectorStore(VectorStore):
    """In-process vector store for tests and local development without Qdrant."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []
        self._dimension: int | None = None

    def ensure_collection(self, dimension: int) -> None:
        self._dimension = dimension

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        id_set = set(ids)
        self._records = [r for r in self._records if r["id"] not in id_set]
        for point_id, vector, payload in zip(ids, vectors, payloads):
            self._records.append({"id": point_id, "vector": vector, "payload": payload})

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in self._records:
            payload = record["payload"]
            if filters:
                if "document_id" in filters and payload.get("document_id") != filters["document_id"]:
                    continue
                if "owner_id" in filters and payload.get("owner_id") != filters["owner_id"]:
                    continue
                if "document_ids" in filters and payload.get("document_id") not in filters["document_ids"]:
                    continue
                if "org_id" in filters and payload.get("org_id") != filters["org_id"]:
                    continue
            score = _cosine_similarity(query_vector, record["vector"])
            scored.append((score, payload))

        scored.sort(key=lambda item: item[0], reverse=True)
        results: list[SearchResult] = []
        for score, payload in scored[:top_k]:
            results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    document_id=int(payload.get("document_id", 0)),
                    filename=payload.get("filename"),
                    page_number=payload.get("page_number"),
                    section=payload.get("section"),
                    similarity_score=round(score, 6),
                    chunk_index=payload.get("chunk_index"),
                    metadata=payload,
                )
            )
        return results

    def delete_by_document(self, document_id: int) -> None:
        self._records = [
            r for r in self._records if r["payload"].get("document_id") != document_id
        ]

    def count(self) -> int:
        return len(self._records)


class QdrantVectorStore(VectorStore):
    """Qdrant vector database backend (primary)."""

    def __init__(self) -> None:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qmodels

        self._models = qmodels
        kwargs: dict[str, Any] = {"url": settings.qdrant_url}
        if settings.qdrant_api_key:
            kwargs["api_key"] = settings.qdrant_api_key
        self.client = QdrantClient(**kwargs)
        self.collection = settings.qdrant_collection

    def ensure_collection(self, dimension: int, collection_name: str | None = None) -> None:
        target = collection_name or self.collection
        existing = {c.name for c in self.client.get_collections().collections}
        if target not in existing:
            self.client.create_collection(
                collection_name=target,
                vectors_config=self._models.VectorParams(
                    size=dimension,
                    distance=self._models.Distance.COSINE,
                ),
            )
        # Ensure payload schema indexes exist for sub-10ms filtered HNSW search
        for field_name in ["org_id", "owner_id", "document_id"]:
            try:
                self.client.create_payload_index(
                    collection_name=target,
                    field_name=field_name,
                    field_schema=self._models.PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                logger.debug("Payload index for %s may already exist: %s", field_name, e)

    def create_shadow_collection(self, shadow_name: str, dimension: int) -> None:
        """Create a new shadow collection for zero-downtime reindexing."""
        self.ensure_collection(dimension=dimension, collection_name=shadow_name)

    def swap_alias(self, alias_name: str, new_collection_name: str, old_collection_name: str | None = None) -> None:
        """Atomically swap alias to point to new shadow collection."""
        actions = [
            self._models.CreateAliasOperation(
                create_alias=self._models.CreateAlias(
                    alias_name=alias_name,
                    collection_name=new_collection_name,
                )
            )
        ]
        if old_collection_name:
            actions.insert(
                0,
                self._models.DeleteAliasOperation(
                    delete_alias=self._models.DeleteAlias(alias_name=alias_name)
                ),
            )
        self.client.update_collection_aliases(change_aliases_operations=actions)

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        points = [
            self._models.PointStruct(
                id=self._to_point_id(point_id),
                vector=vector,
                payload={**payload, "point_key": point_id},
            )
            for point_id, vector, payload in zip(ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        query_filter = self._build_filter(filters)
        hits = self.client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        results: list[SearchResult] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    document_id=int(payload.get("document_id", 0)),
                    filename=payload.get("filename"),
                    page_number=payload.get("page_number"),
                    section=payload.get("section"),
                    similarity_score=round(float(hit.score), 6),
                    chunk_index=payload.get("chunk_index"),
                    metadata=payload,
                )
            )
        return results

    def delete_by_document(self, document_id: int) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=self._models.FilterSelector(
                filter=self._models.Filter(
                    must=[
                        self._models.FieldCondition(
                            key="document_id",
                            match=self._models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )

    def count(self) -> int:
        info = self.client.get_collection(self.collection)
        return int(info.points_count or 0)

    def _build_filter(self, filters: dict[str, Any] | None):
        if not filters:
            return None
        conditions = []
        if "document_id" in filters:
            conditions.append(
                self._models.FieldCondition(
                    key="document_id",
                    match=self._models.MatchValue(value=filters["document_id"]),
                )
            )
        if "owner_id" in filters:
            conditions.append(
                self._models.FieldCondition(
                    key="owner_id",
                    match=self._models.MatchValue(value=filters["owner_id"]),
                )
            )
        if "document_ids" in filters:
            conditions.append(
                self._models.FieldCondition(
                    key="document_id",
                    match=self._models.MatchAny(any=list(filters["document_ids"])),
                )
            )
        if "org_id" in filters:
            conditions.append(
                self._models.FieldCondition(
                    key="org_id",
                    match=self._models.MatchValue(value=filters["org_id"]),
                )
            )
        if not conditions:
            return None
        return self._models.Filter(must=conditions)

    @staticmethod
    def _to_point_id(point_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, point_id))


class ChromaVectorStore(VectorStore):
    """ChromaDB backend for local development."""

    def __init__(self) -> None:
        import chromadb

        self.client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.collection_name = settings.qdrant_collection
        self._collection = None

    def ensure_collection(self, dimension: int) -> None:
        try:
            existing = self.client.get_collection(name=self.collection_name)
            existing_dim = existing.metadata.get("dimension") if existing.metadata else None

            # Treat "no dimension recorded" the same as "mismatched dimension" —
            # an untracked collection cannot be assumed compatible with the
            # currently configured embedding provider/dimension.
            if existing_dim is None or int(existing_dim) != dimension:
                reason = (
                    "no dimension metadata recorded (likely created before "
                    "dimension tracking existed, or under a different embedding provider)"
                    if existing_dim is None
                    else f"dimension mismatch ({existing_dim} vs {dimension})"
                )
                logger.warning(
                    "ChromaDB collection '%s': %s. Deleting and recreating collection. "
                    "All previously indexed documents must be re-indexed.",
                    self.collection_name, reason,
                )
                self.client.delete_collection(name=self.collection_name)
                self._collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine", "dimension": dimension},
                )
            else:
                self._collection = existing
        except Exception:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "dimension": dimension},
            )

    @property
    def collection(self):
        if self._collection is None:
            self.ensure_collection(settings.embedding_dimension)
        return self._collection

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        documents = [p.get("text", "") for p in payloads]
        metadatas = []
        for payload in payloads:
            meta = {
                k: ("" if v is None else v)
                for k, v in payload.items()
                if k != "text" and isinstance(v, (str, int, float, bool))
            }
            metadatas.append(meta)
        self.collection.upsert(
            ids=ids,
            embeddings=vectors,
            documents=documents,
            metadatas=metadatas,
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        where = None
        if filters:
            clauses = []
            if "document_id" in filters:
                clauses.append({"document_id": {"$eq": filters["document_id"]}})
            if "owner_id" in filters:
                clauses.append({"owner_id": {"$eq": filters["owner_id"]}})
            if "org_id" in filters:
                clauses.append({"org_id": {"$eq": filters["org_id"]}})
            if "document_ids" in filters and filters["document_ids"]:
                # ChromaDB $in operator for list-based document ID filtering
                clauses.append({"document_id": {"$in": [int(d) for d in filters["document_ids"]]}})
            if len(clauses) == 1:
                where = clauses[0]
            elif len(clauses) > 1:
                where = {"$and": clauses}

        response = self.collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        results: list[SearchResult] = []
        docs = (response.get("documents") or [[]])[0]
        metas = (response.get("metadatas") or [[]])[0]
        distances = (response.get("distances") or [[]])[0]

        for text, meta, distance in zip(docs, metas, distances):
            meta = meta or {}
            score = 1.0 - float(distance)
            results.append(
                SearchResult(
                    text=text or "",
                    document_id=int(meta.get("document_id", 0)),
                    filename=meta.get("filename") or None,
                    page_number=meta.get("page_number") if meta.get("page_number") != "" else None,
                    section=meta.get("section") or None,
                    similarity_score=round(score, 6),
                    chunk_index=meta.get("chunk_index") if meta.get("chunk_index") != "" else None,
                    metadata=meta,
                )
            )
        return results

    def delete_by_document(self, document_id: int) -> None:
        self.collection.delete(where={"document_id": document_id})

    def count(self) -> int:
        return int(self.collection.count())


class PineconeVectorStore(VectorStore):
    """Pinecone cloud vector database backend."""

    def __init__(self) -> None:
        if not settings.pinecone_api_key or not settings.pinecone_index:
            raise ValueError("PINECONE_API_KEY and PINECONE_INDEX are required")

        from pinecone import Pinecone

        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.index = self.pc.Index(settings.pinecone_index)
        self.namespace = settings.pinecone_namespace

    def ensure_collection(self, dimension: int) -> None:
        # Index is managed in Pinecone console / infra
        return

    def upsert(
        self,
        ids: list[str],
        vectors: list[list[float]],
        payloads: list[dict[str, Any]],
    ) -> None:
        records = [
            {"id": point_id, "values": vector, "metadata": _pinecone_safe_metadata(payload)}
            for point_id, vector, payload in zip(ids, vectors, payloads)
        ]
        self.index.upsert(vectors=records, namespace=self.namespace)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        pinecone_filter = None
        if filters:
            pinecone_filter = {}
            if "document_id" in filters:
                pinecone_filter["document_id"] = {"$eq": filters["document_id"]}
            if "owner_id" in filters:
                pinecone_filter["owner_id"] = {"$eq": filters["owner_id"]}
            if "org_id" in filters:
                pinecone_filter["org_id"] = {"$eq": filters["org_id"]}

        response = self.index.query(
            vector=query_vector,
            top_k=top_k,
            include_metadata=True,
            namespace=self.namespace,
            filter=pinecone_filter or None,
        )
        results: list[SearchResult] = []
        for match in response.get("matches", []):
            payload = match.get("metadata") or {}
            results.append(
                SearchResult(
                    text=payload.get("text", ""),
                    document_id=int(payload.get("document_id", 0)),
                    filename=payload.get("filename"),
                    page_number=payload.get("page_number"),
                    section=payload.get("section"),
                    similarity_score=round(float(match.get("score", 0.0)), 6),
                    chunk_index=payload.get("chunk_index"),
                    metadata=payload,
                )
            )
        return results

    def delete_by_document(self, document_id: int) -> None:
        self.index.delete(
            filter={"document_id": {"$eq": document_id}},
            namespace=self.namespace,
        )

    def count(self) -> int:
        stats = self.index.describe_index_stats()
        namespaces = stats.get("namespaces") or {}
        ns_stats = namespaces.get(self.namespace) or {}
        return int(ns_stats.get("vector_count", 0))


_STORE_SINGLETON: VectorStore | None = None


def get_vector_store(force_new: bool = False) -> VectorStore:
    """Factory / singleton for configured vector store."""
    global _STORE_SINGLETON
    if _STORE_SINGLETON is not None and not force_new:
        return _STORE_SINGLETON

    name = settings.vector_store.lower()
    if name == "memory":
        store: VectorStore = InMemoryVectorStore()
    elif name == "qdrant":
        store = QdrantVectorStore()
    elif name == "chroma":
        store = ChromaVectorStore()
    elif name == "pinecone":
        store = PineconeVectorStore()
    else:
        raise ValueError(
            f"Unknown vector store '{name}'. Supported: qdrant, chroma, pinecone, memory"
        )

    _STORE_SINGLETON = store
    return store


def reset_vector_store() -> None:
    """Clear singleton (used in tests)."""
    global _STORE_SINGLETON
    _STORE_SINGLETON = None


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        logger.error(
            "Cosine similarity dimension mismatch: query vector has %d dims, "
            "stored vector has %d dims. This indicates an embedding provider/dimension "
            "change without re-indexing. Returning 0.0 (fails grounding checks).",
            len(a), len(b),
        )
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


def _pinecone_safe_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe
