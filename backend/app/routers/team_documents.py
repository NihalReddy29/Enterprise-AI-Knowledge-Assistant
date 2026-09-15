"""Team-scoped document upload, list, and delete."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from app.models.team import Team
from app.models.user import Document, DocumentStatus
from app.schemas.document import DocumentListResponse, DocumentResponse, DocumentUploadResponse
from app.services.indexing import get_indexing_service
from app.services.storage import get_storage_backend
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.file_validator import validate_upload_file
from app.utils.sanitizer import sanitize_filename
from app.utils.team_dependencies import get_team_membership_row, get_team_or_404, require_team_admin
from app.workers.document_worker import process_document

router = APIRouter(prefix="/teams", tags=["Team Documents"])


def _get_team_document(db: DbSession, team_id: int, document_id: int) -> Document:
    document = (
        db.query(Document)
        .filter(Document.id == document_id, Document.team_id == team_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post(
    "/{team_id}/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document to the team knowledge base",
)
async def upload_team_document(
    team_id: int,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> DocumentUploadResponse:
    """Upload a document to the team's isolated knowledge base (any active member)."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )
    get_team_or_404(db, team_id)

    file_data = await file.read()
    file_type = validate_upload_file(file, len(file_data))

    storage = get_storage_backend()
    safe_filename = sanitize_filename(file.filename or "document")
    storage_path = storage.generate_path(team_id, safe_filename, prefix="teams")

    document = Document(
        filename=safe_filename,
        file_type=file_type,
        owner_id=current_user.id,
        team_id=team_id,
        storage_path=storage_path,
        file_size=len(file_data),
        status=DocumentStatus.PENDING,
    )
    storage.save(file_data, storage_path)
    db.add(document)
    db.commit()
    db.refresh(document)

    background_tasks.add_task(process_document, document.id)

    return DocumentUploadResponse(
        document=DocumentResponse.model_validate(document),
        message="Document uploaded to team knowledge base and queued for processing",
    )


@router.get(
    "/{team_id}/documents",
    response_model=DocumentListResponse,
    summary="List team documents",
)
def list_team_documents(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 50,
) -> DocumentListResponse:
    """List documents in the team's knowledge base."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    query = db.query(Document).filter(Document.team_id == team_id)
    total = query.count()
    documents = (
        query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
    )
    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.delete(
    "/{team_id}/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a team document",
)
def delete_team_document(
    team_id: int,
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a team document (admin or uploader)."""
    membership = get_team_membership_row(db, team_id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    document = _get_team_document(db, team_id, document_id)
    is_admin = membership.role.value in {"owner", "admin"}
    if document.owner_id != current_user.id and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the uploader or a team admin can delete this document",
        )

    team = db.query(Team).filter(Team.id == team_id).first()
    indexing = get_indexing_service()
    if document.status == DocumentStatus.INDEXED and team:
        indexing.delete_document(document.id, collection_name=team.qdrant_collection_name)

    storage = get_storage_backend()
    try:
        storage.delete(document.storage_path)
        if document.extracted_text_path:
            storage.delete(document.extracted_text_path)
    except Exception:
        pass

    db.delete(document)
    db.commit()
