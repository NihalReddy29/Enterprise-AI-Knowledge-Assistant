"""Recursive character text splitter with metadata preservation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.config import get_settings
from app.services.document_processor import ExtractionResult

settings = get_settings()


@dataclass
class DocumentChunk:
    """A text chunk with citation metadata."""

    document_id: int
    chunk_index: int
    text: str
    page_number: int | None = None
    section: str | None = None
    filename: str | None = None
    file_type: str | None = None
    owner_id: int | None = None

    def to_metadata(self) -> dict[str, Any]:
        """Return metadata suitable for vector store payloads."""
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section,
            "filename": self.filename,
            "file_type": self.file_type,
            "owner_id": self.owner_id,
            "text": self.text,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecursiveCharacterTextSplitter:
    """Split text using a hierarchy of separators (paragraph → line → word → char)."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ) -> None:
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
        self.separators = separators or [
            "\n# ",
            "\n## ",
            "\n### ",
            "\n\n",
            "\n|",
            "\n- ",
            "\n* ",
            "\n",
            ". ",
            " ",
            "",
        ]

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    def split_text(self, text: str) -> list[str]:
        """Split raw text into overlapping chunks."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= self.chunk_size:
            return [text]
        return self._split_recursive(text, self.separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        separator = separators[0] if separators else ""
        remaining = separators[1:] if separators else []

        if separator == "":
            return self._chunk_by_size(text)

        parts = text.split(separator)
        good_parts: list[str] = []
        current = ""

        for part in parts:
            candidate = part if not current else current + separator + part
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            if current:
                good_parts.append(current)
            if len(part) > self.chunk_size:
                good_parts.extend(self._split_recursive(part, remaining))
                current = ""
            else:
                current = part

        if current:
            good_parts.append(current)

        return self._merge_with_overlap(good_parts)

    def _chunk_by_size(self, text: str) -> list[str]:
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = max(0, end - self.chunk_overlap)
        return chunks

    def _merge_with_overlap(self, parts: list[str]) -> list[str]:
        if not parts:
            return []

        chunks: list[str] = []
        current = parts[0]

        for part in parts[1:]:
            separator = "\n\n" if "\n" in current or "\n" in part else " "
            candidate = f"{current}{separator}{part}" if current else part
            if len(candidate) <= self.chunk_size:
                current = candidate
                continue

            chunks.append(current)
            if self.chunk_overlap > 0 and len(current) > self.chunk_overlap:
                overlap = current[-self.chunk_overlap :]
                current = f"{overlap}{separator}{part}"
                if len(current) > self.chunk_size:
                    current = part
            else:
                current = part

        if current:
            chunks.append(current)
        return chunks


class ChunkingService:
    """Create document chunks from extraction results."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def chunk_extraction(
        self,
        result: ExtractionResult,
        document_id: int,
        filename: str,
        owner_id: int,
    ) -> list[DocumentChunk]:
        """Chunk each page/section while preserving metadata."""
        chunks: list[DocumentChunk] = []
        chunk_index = 0

        for page in result.pages:
            if not page.text or not page.text.strip():
                continue

            texts = self.splitter.split_text(page.text)
            for text in texts:
                chunks.append(
                    DocumentChunk(
                        document_id=document_id,
                        chunk_index=chunk_index,
                        text=text,
                        page_number=page.page_number,
                        section=page.section,
                        filename=filename,
                        file_type=result.file_type,
                        owner_id=owner_id,
                    )
                )
                chunk_index += 1

        return chunks


def get_chunking_service() -> ChunkingService:
    """Return configured chunking service."""
    return ChunkingService()
