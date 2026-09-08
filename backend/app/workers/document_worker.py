"""Background document processing worker."""

import logging
from datetime import datetime, timezone

from app.database import session as db_module
from app.models.user import Document, DocumentStatus
from app.services.document_processor import get_document_processor
from app.services.indexing import get_indexing_service
from app.services.storage import get_storage_backend

logger = logging.getLogger(__name__)


def process_document(document_id: int) -> None:
    """Process a document: extract text, chunk, embed, and index vectors.

    This runs as a background task after upload.
    """
    storage = get_storage_backend()
    processor = get_document_processor()
    indexing = get_indexing_service()

    # Use context manager so the session is always closed, even on unexpected errors
    with db_module.SessionLocal() as db:
        try:
            document = db.query(Document).filter(Document.id == document_id).first()
            if not document:
                logger.error("Document %d not found for processing", document_id)
                return

            document.status = DocumentStatus.PROCESSING
            document.error_message = None
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            file_data = storage.read(document.storage_path)
            result = processor.process(file_data, document.file_type)

            if not result.full_text.strip():
                raise ValueError("No text could be extracted from the document")

            extracted_path = processor.save_extraction_result(
                result, storage, document.owner_id, document.id
            )

            document.extracted_text_path = extracted_path
            document.page_count = result.total_pages
            document.status = DocumentStatus.EXTRACTED
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            index_result = indexing.index_document(
                result=result,
                document_id=document.id,
                filename=document.filename,
                owner_id=document.owner_id,
                org_id=document.org_id,
            )

            document.chunk_count = index_result.chunk_count
            document.status = DocumentStatus.INDEXED
            document.updated_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "Document %d indexed: %d pages, %d chunks, OCR=%s",
                document_id,
                result.total_pages,
                index_result.chunk_count,
                result.ocr_used,
            )

        except Exception as exc:
            logger.exception("Failed to process document %d", document_id)
            db.rollback()
            # Re-fetch document in case the session state is dirty
            document = db.query(Document).filter(Document.id == document_id).first()
            if document:
                document.status = DocumentStatus.FAILED
                document.error_message = str(exc)[:2000]
                document.updated_at = datetime.now(timezone.utc)
                db.commit()
