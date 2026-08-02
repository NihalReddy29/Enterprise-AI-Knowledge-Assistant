"""Document management routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, UploadFile, status
from fastapi.responses import Response

from app.models.user import Document, DocumentStatus, User, UserRole
from app.schemas.document import (
    DocumentContentResponse,
    DocumentHighlightResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
    ExtractedPageResponse,
    HighlightMatch,
)
from app.services.document_processor import get_document_processor
from app.services.storage import get_storage_backend
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.file_validator import validate_upload_file
from app.utils.highlight import find_highlight_spans
from app.utils.sanitizer import sanitize_filename
from app.workers.document_worker import process_document

router = APIRouter(prefix="/documents", tags=["Documents"])

MIME_BY_TYPE = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain; charset=utf-8",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "tiff": "image/tiff",
    "bmp": "image/bmp",
}


def _can_access_document(user: User, document: Document) -> bool:
    """Employees can only access their own documents; admins can access all."""
    return user.role == UserRole.ADMIN or document.owner_id == user.id


def _get_accessible_document(db: DbSession, document_id: int, user: User) -> Document:
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if not _can_access_document(user, document):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return document


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentUploadResponse:
    """Upload a document file. Processing runs in the background."""
    file_data = await file.read()
    file_type = validate_upload_file(file, len(file_data))

    storage = get_storage_backend()
    safe_filename = sanitize_filename(file.filename or "document")
    storage_path = storage.generate_path(current_user.id, safe_filename)
    storage.save(file_data, storage_path)

    document = Document(
        filename=safe_filename,
        file_type=file_type,
        owner_id=current_user.id,
        storage_path=storage_path,
        file_size=len(file_data),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document, document.id)

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        message="Document uploaded and queued for processing",
    )


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List documents",
)
def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
) -> DocumentListResponse:
    """List documents. Admins see all; employees see only their own."""
    query = db.query(Document)
    if current_user.role != UserRole.ADMIN:
        query = query.filter(Document.owner_id == current_user.id)

    total = query.count()
    documents = (
        query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get document metadata",
)
def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Document:
    """Get metadata for a single document."""
    return _get_accessible_document(db, document_id, current_user)


@router.get(
    "/{document_id}/file",
    summary="Download/view original document file",
)
def get_document_file(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """Stream the original uploaded file for the source viewer."""
    document = _get_accessible_document(db, document_id, current_user)
    storage = get_storage_backend()
    try:
        file_data = storage.read(document.storage_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored file not found",
        ) from exc

    media_type = MIME_BY_TYPE.get(document.file_type.lower(), "application/octet-stream")
    headers = {
        "Content-Disposition": f'inline; filename="{document.filename}"',
        "Cache-Control": "private, max-age=60",
    }
    return Response(content=file_data, media_type=media_type, headers=headers)


@router.get(
    "/{document_id}/highlight",
    response_model=DocumentHighlightResponse,
    summary="Get highlight metadata for a citation excerpt",
)
def get_document_highlight(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
    excerpt: str = Query(..., min_length=1, max_length=4000),
    page_number: int | None = Query(default=None, ge=1),
    section: str | None = Query(default=None, max_length=512),
) -> DocumentHighlightResponse:
    """Locate citation text within extracted page content for highlighting."""
    document = _get_accessible_document(db, document_id, current_user)

    if document.status not in (DocumentStatus.EXTRACTED, DocumentStatus.INDEXED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready. Current status: {document.status.value}",
        )
    if not document.extracted_text_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted content not found",
        )

    storage = get_storage_backend()
    processor = get_document_processor()
    result = processor.load_extraction_result(storage, document.extracted_text_path)

    target_page = None
    if page_number is not None:
        target_page = next((p for p in result.pages if p.page_number == page_number), None)

    if target_page is None and section:
        target_page = next(
            (p for p in result.pages if p.section and section.lower() in p.section.lower()),
            None,
        )

    if target_page is None:
        # Choose the page with the best excerpt match
        best_score = -1
        for page in result.pages:
            spans = find_highlight_spans(page.text, excerpt)
            score = sum(span.end - span.start for span in spans)
            if score > best_score:
                best_score = score
                target_page = page

    if target_page is None and result.pages:
        target_page = result.pages[0]

    if target_page is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extractable pages found for highlighting",
        )

    spans = find_highlight_spans(target_page.text, excerpt)
    return DocumentHighlightResponse(
        document_id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        page_number=target_page.page_number,
        section=target_page.section or section,
        page_text=target_page.text,
        excerpt=excerpt,
        matches=[
            HighlightMatch(start=s.start, end=s.end, matched_text=s.matched_text) for s in spans
        ],
        total_pages=result.total_pages,
    )


@router.get(
    "/{document_id}/content",
    response_model=DocumentContentResponse,
    summary="Get extracted document content",
)
def get_document_content(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentContentResponse:
    """Return extracted text content for a processed document."""
    document = _get_accessible_document(db, document_id, current_user)

    if document.status not in (DocumentStatus.EXTRACTED, DocumentStatus.INDEXED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is not ready. Current status: {document.status.value}",
        )

    if not document.extracted_text_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Extracted content not found",
        )

    storage = get_storage_backend()
    processor = get_document_processor()
    result = processor.load_extraction_result(storage, document.extracted_text_path)

    return DocumentContentResponse(
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        pages=[
            ExtractedPageResponse(
                page_number=p.page_number,
                text=p.text,
                section=p.section,
                ocr_used=p.ocr_used,
            )
            for p in result.pages
        ],
        total_pages=result.total_pages,
        ocr_used=result.ocr_used,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document",
)
def delete_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a document and its stored files."""
    document = _get_accessible_document(db, document_id, current_user)

    storage = get_storage_backend()
    storage.delete(document.storage_path)
    if document.extracted_text_path:
        storage.delete(document.extracted_text_path)

    try:
        from app.services.indexing import get_indexing_service

        get_indexing_service().delete_document(document.id)
    except Exception:
        # Vector cleanup should not block document deletion
        pass

    db.delete(document)
    db.commit()
