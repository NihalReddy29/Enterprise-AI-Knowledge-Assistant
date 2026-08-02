"""Semantic search routes."""

from fastapi import APIRouter

from app.models.user import UserRole
from app.schemas.search import SearchHit, SearchRequest, SearchResponse
from app.services.indexing import get_indexing_service
from app.utils.dependencies import CurrentUser
from app.utils.sanitizer import sanitize_text

router = APIRouter(prefix="/search", tags=["Search"])


@router.post(
    "/",
    response_model=SearchResponse,
    summary="Semantic search over indexed documents",
)
def semantic_search(
    payload: SearchRequest,
    current_user: CurrentUser,
) -> SearchResponse:
    """Embed the query and retrieve top-K similar document chunks."""
    query = sanitize_text(payload.query, max_length=2000)
    indexing = get_indexing_service()

    owner_filter = None if current_user.role == UserRole.ADMIN else current_user.id

    results = indexing.search(
        query=query,
        top_k=payload.top_k,
        owner_id=owner_filter,
        document_ids=payload.document_ids,
    )

    hits = [
        SearchHit(
            text=item.text,
            document=item.filename,
            document_id=item.document_id,
            page_number=item.page_number,
            section=item.section,
            similarity_score=item.similarity_score,
            chunk_index=item.chunk_index,
        )
        for item in results
    ]

    return SearchResponse(query=query, results=hits, total=len(hits))
