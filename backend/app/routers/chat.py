"""Chat and RAG query routes."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload

from app.models.user import Conversation, Feedback, Message, MessageRole, QueryLog, UserRole
from app.schemas.admin import FeedbackCreateRequest, FeedbackResponse
from app.schemas.chat import (
    ChatQueryRequest,
    ChatQueryResponse,
    CitationSchema,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
)
from app.services.rag import get_rag_service
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.sanitizer import sanitize_text
from app.utils.topics import extract_topic

router = APIRouter(prefix="/chat", tags=["Chat"])


def _conversation_title(question: str) -> str:
    cleaned = " ".join(question.strip().split())
    return cleaned[:80] if cleaned else "New Conversation"


def _get_user_conversation(
    db: DbSession,
    conversation_id: int,
    user_id: int,
    is_admin: bool,
) -> Conversation:
    conversation = (
        db.query(Conversation)
        .options(joinedload(Conversation.messages))
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if not is_admin and conversation.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return conversation


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    summary="Ask a question using RAG",
)
def chat_query(
    payload: ChatQueryRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> ChatQueryResponse:
    """Retrieve context, generate an answer with citations, and persist the exchange."""
    question = sanitize_text(payload.question, max_length=4000)
    is_admin = current_user.role == UserRole.ADMIN

    if payload.conversation_id:
        conversation = _get_user_conversation(
            db, payload.conversation_id, current_user.id, is_admin
        )
    else:
        conversation = Conversation(
            user_id=current_user.id,
            title=_conversation_title(question),
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in conversation.messages
    ]

    owner_filter = None if is_admin else current_user.id
    rag = get_rag_service()
    result = rag.ask(
        question=question,
        owner_id=owner_filter,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
        chat_history=history,
        compare_mode=payload.compare,
    )

    citations_data = [c.to_dict() for c in result.citations]

    user_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=question,
    )
    assistant_message = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=result.answer,
        citations=citations_data,
    )
    db.add(user_message)
    db.add(assistant_message)
    db.flush()

    db.add(
        QueryLog(
            user_id=current_user.id,
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            question=question,
            topic=extract_topic(question),
            provider=result.provider,
            citation_count=len(citations_data),
            insufficient_information=result.insufficient_information,
        )
    )

    if conversation.title == "New Conversation":
        conversation.title = _conversation_title(question)

    db.commit()
    db.refresh(assistant_message)

    return ChatQueryResponse(
        conversation_id=conversation.id,
        question=question,
        answer=result.answer,
        citations=[CitationSchema(**c) for c in citations_data],
        message_id=assistant_message.id,
        provider=result.provider,
        model=result.model,
        insufficient_information=result.insufficient_information,
    )


@router.get(
    "/conversations",
    response_model=ConversationListResponse,
    summary="List conversations",
)
def list_conversations(
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationListResponse:
    """Return conversations for the current user."""
    query = db.query(Conversation).filter(Conversation.user_id == current_user.id)
    conversations = query.order_by(Conversation.created_at.desc()).all()
    return ConversationListResponse(
        conversations=[ConversationResponse.model_validate(c) for c in conversations],
        total=len(conversations),
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation with messages",
)
def get_conversation(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationDetailResponse:
    """Return a conversation and its message history."""
    conversation = _get_user_conversation(
        db,
        conversation_id,
        current_user.id,
        current_user.role == UserRole.ADMIN,
    )
    messages = [
        MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role.value,
            content=msg.content,
            citations=[CitationSchema(**c) for c in (msg.citations or [])] or None,
            created_at=msg.created_at,
        )
        for msg in conversation.messages
    ]
    return ConversationDetailResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=messages,
    )


@router.get(
    "/history",
    response_model=ConversationListResponse,
    summary="Alias for conversation list",
)
def get_chat_history(
    db: DbSession,
    current_user: CurrentUser,
) -> ConversationListResponse:
    """Compatibility endpoint for chat history listing."""
    return list_conversations(db=db, current_user=current_user)


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
def delete_conversation(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a conversation and all of its messages."""
    conversation = _get_user_conversation(
        db,
        conversation_id,
        current_user.id,
        current_user.role == UserRole.ADMIN,
    )
    db.delete(conversation)
    db.commit()


@router.post(
    "/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit feedback for an assistant message",
)
def submit_feedback(
    message_id: int,
    payload: FeedbackCreateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Feedback:
    """Store helpful / not helpful rating for an assistant answer."""
    message = db.query(Message).filter(Message.id == message_id).first()
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if message.role != MessageRole.ASSISTANT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback is only allowed on assistant messages",
        )

    conversation = (
        db.query(Conversation).filter(Conversation.id == message.conversation_id).first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    if current_user.role != UserRole.ADMIN and conversation.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    existing = db.query(Feedback).filter(Feedback.message_id == message_id).first()
    comment = sanitize_text(payload.comment, max_length=2000) if payload.comment else None
    if existing:
        existing.rating = payload.rating
        existing.comment = comment
        db.commit()
        db.refresh(existing)
        return existing

    feedback = Feedback(
        message_id=message_id,
        rating=payload.rating,
        comment=comment,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback
