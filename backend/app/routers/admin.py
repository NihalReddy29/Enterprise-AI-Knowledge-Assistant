"""Admin dashboard routes."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func

from app.models.user import (
    Conversation,
    Document,
    DocumentStatus,
    Feedback,
    Message,
    QueryLog,
    User,
    UserRole,
)
from app.schemas.admin import (
    AdminDocumentListResponse,
    AdminStatistics,
    FeedbackAdminItem,
    FeedbackListResponse,
    QueryLogListResponse,
    QueryLogResponse,
    StorageBreakdown,
    StorageStats,
    TopicStat,
)
from app.schemas.document import DocumentResponse
from app.schemas.user import UserListResponse
from app.utils.dependencies import AdminUser, DbSession

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/users",
    response_model=UserListResponse,
    summary="List all users (admin only)",
)
def list_users(db: DbSession, _: AdminUser) -> UserListResponse:
    """Return all registered users."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return UserListResponse(users=users, total=len(users))


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user (admin only)",
)
def delete_user(user_id: int, db: DbSession, admin: AdminUser) -> None:
    """Delete a user and cascaded documents/conversations."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own admin account",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    remaining_admins = (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.id != user_id)
        .count()
    )
    if user.role == UserRole.ADMIN and remaining_admins == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the last admin user",
        )

    db.delete(user)
    db.commit()


@router.get(
    "/documents",
    response_model=AdminDocumentListResponse,
    summary="List all uploaded documents",
)
def list_all_documents(
    db: DbSession,
    _: AdminUser,
    skip: int = 0,
    limit: int = 100,
) -> AdminDocumentListResponse:
    """Return documents across all users."""
    total = db.query(Document).count()
    documents = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return AdminDocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=total,
    )


@router.get(
    "/storage",
    response_model=StorageStats,
    summary="Monitor document storage usage",
)
def get_storage_stats(db: DbSession, _: AdminUser) -> StorageStats:
    """Aggregate storage by status and file type."""
    total_documents = db.query(Document).count()
    total_bytes = db.query(func.coalesce(func.sum(Document.file_size), 0)).scalar() or 0

    by_status_rows = (
        db.query(Document.status, func.count(Document.id))
        .group_by(Document.status)
        .all()
    )
    by_status = {status.value: count for status, count in by_status_rows}

    by_type_rows = (
        db.query(
            Document.file_type,
            func.count(Document.id),
            func.coalesce(func.sum(Document.file_size), 0),
        )
        .group_by(Document.file_type)
        .order_by(func.sum(Document.file_size).desc())
        .all()
    )
    by_type = [
        StorageBreakdown(file_type=file_type, count=count, total_bytes=int(size))
        for file_type, count, size in by_type_rows
    ]

    return StorageStats(
        total_documents=total_documents,
        total_bytes=int(total_bytes),
        total_mb=round(int(total_bytes) / (1024 * 1024), 2),
        by_status=by_status,
        by_type=by_type,
    )


@router.get(
    "/queries",
    response_model=QueryLogListResponse,
    summary="View recent user queries",
)
def list_queries(
    db: DbSession,
    _: AdminUser,
    skip: int = 0,
    limit: int = 50,
) -> QueryLogListResponse:
    """Return recent RAG questions with user metadata."""
    total = db.query(QueryLog).count()
    rows = (
        db.query(QueryLog, User)
        .join(User, User.id == QueryLog.user_id)
        .order_by(QueryLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    queries = [
        QueryLogResponse(
            id=log.id,
            user_id=log.user_id,
            conversation_id=log.conversation_id,
            message_id=log.message_id,
            question=log.question,
            topic=log.topic,
            provider=log.provider,
            citation_count=log.citation_count,
            insufficient_information=log.insufficient_information,
            created_at=log.created_at,
            user_email=user.email,
            user_name=user.name,
        )
        for log, user in rows
    ]
    return QueryLogListResponse(queries=queries, total=total)


@router.get(
    "/feedback",
    response_model=FeedbackListResponse,
    summary="View answer feedback",
)
def list_feedback(
    db: DbSession,
    _: AdminUser,
    skip: int = 0,
    limit: int = 50,
) -> FeedbackListResponse:
    """Return feedback entries with related message/user context."""
    total = db.query(Feedback).count()
    rows = (
        db.query(Feedback, Message, User)
        .join(Message, Message.id == Feedback.message_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .join(User, User.id == Conversation.user_id)
        .order_by(Feedback.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        FeedbackAdminItem(
            id=feedback.id,
            message_id=feedback.message_id,
            rating=feedback.rating,
            comment=feedback.comment,
            created_at=feedback.created_at,
            message_content=message.content[:300],
            user_email=user.email,
        )
        for feedback, message, user in rows
    ]
    return FeedbackListResponse(feedback=items, total=total)


@router.get(
    "/statistics",
    response_model=AdminStatistics,
    summary="Get platform statistics (admin only)",
)
def get_statistics(db: DbSession, _: AdminUser) -> AdminStatistics:
    """Return analytics for the admin dashboard."""
    total_users = db.query(User).count()
    total_documents = db.query(Document).count()
    total_questions = db.query(QueryLog).count()
    total_conversations = db.query(Conversation).count()
    total_feedback = db.query(Feedback).count()
    helpful_feedback = db.query(Feedback).filter(Feedback.rating == 1).count()
    not_helpful_feedback = db.query(Feedback).filter(Feedback.rating == 0).count()
    indexed_documents = (
        db.query(Document).filter(Document.status == DocumentStatus.INDEXED).count()
    )
    failed_documents = (
        db.query(Document).filter(Document.status == DocumentStatus.FAILED).count()
    )
    storage_bytes = int(db.query(func.coalesce(func.sum(Document.file_size), 0)).scalar() or 0)

    topic_rows = (
        db.query(QueryLog.topic, func.count(QueryLog.id))
        .filter(QueryLog.topic.isnot(None))
        .group_by(QueryLog.topic)
        .order_by(func.count(QueryLog.id).desc())
        .limit(8)
        .all()
    )
    # Fallback: derive from questions if topic column empty historically
    if not topic_rows:
        from app.utils.topics import top_topics

        questions = [q for (q,) in db.query(QueryLog.question).all()]
        topic_rows = top_topics(questions, limit=8)

    most_searched_topics = [
        TopicStat(topic=topic or "general", count=int(count))
        for topic, count in topic_rows
    ]

    return AdminStatistics(
        total_users=total_users,
        total_documents=total_documents,
        total_questions=total_questions,
        total_conversations=total_conversations,
        total_feedback=total_feedback,
        helpful_feedback=helpful_feedback,
        not_helpful_feedback=not_helpful_feedback,
        indexed_documents=indexed_documents,
        failed_documents=failed_documents,
        storage_bytes=storage_bytes,
        storage_mb=round(storage_bytes / (1024 * 1024), 2),
        most_searched_topics=most_searched_topics,
    )
