"""Chat and RAG query routes."""

import json
import logging

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import joinedload

from app.database import session as db_session_module
from app.models.user import Conversation, Feedback, Message, MessageRole, OrgMember, QueryLog, UserRole
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

import asyncio
from collections import defaultdict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat"])

_TENANT_SEMAPHORES: dict[int | None, asyncio.Semaphore] = {}

def _get_tenant_semaphore(org_id: int | None) -> asyncio.Semaphore:
    """Retrieve or lazily create a concurrency semaphore bound to the current event loop."""
    if org_id not in _TENANT_SEMAPHORES:
        capacity = 5 if org_id is not None else 10
        _TENANT_SEMAPHORES[org_id] = asyncio.Semaphore(capacity)
    return _TENANT_SEMAPHORES[org_id]


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
async def chat_query(
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

    if payload.org_id:
        if not is_admin:
            mem = (
                db.query(OrgMember)
                .filter(OrgMember.org_id == payload.org_id, OrgMember.user_id == current_user.id)
                .first()
            )
            if not mem:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of the target organization",
                )
        owner_filter = None
    else:
        owner_filter = None if is_admin else current_user.id

    # Queue discipline: acquire tenant semaphore to prevent LLM API overload
    sem = _get_tenant_semaphore(payload.org_id)
    async with sem:
        rag = get_rag_service()
        result = rag.ask(
            question=question,
            owner_id=owner_filter,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
            chat_history=history,
            compare_mode=payload.compare,
            org_id=payload.org_id,
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


@router.post(
    "/stream",
    summary="Ask a question with streaming SSE response",
    response_class=StreamingResponse,
)
def chat_stream(
    payload: ChatQueryRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Stream token-by-token RAG answer via Server-Sent Events.

    Each event is one of:
    - ``data: {"token": "<text>"}`` — a partial token
    - ``data: [DONE] {"answer": ..., "citations": ..., "conversation_id": ..., ...}``
    """
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

    if payload.org_id:
        if not is_admin:
            mem = (
                db.query(OrgMember)
                .filter(OrgMember.org_id == payload.org_id, OrgMember.user_id == current_user.id)
                .first()
            )
            if not mem:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of the target organization",
                )
        owner_filter = None
    else:
        owner_filter = None if is_admin else current_user.id

    conversation_id = conversation.id
    user_id = current_user.id
    rag = get_rag_service()

    def event_generator():
        # Yield a keepalive so the browser doesn't time out immediately
        yield ": keepalive\n\n"

        accumulated_tokens = ""
        done_payload: dict = {}

        for event in rag.ask_stream(
            question=question,
            owner_id=owner_filter,
            document_ids=payload.document_ids,
            top_k=payload.top_k,
            chat_history=history,
            compare_mode=payload.compare,
            org_id=payload.org_id,
        ):
            if event.startswith("data: [DONE]"):
                raw_json = event[len("data: [DONE] "):].strip()
                done_payload = json.loads(raw_json)
                yield event
            elif event.startswith("data: [CORRECTION]"):
                yield event
            else:
                # Regular token — accumulate
                try:
                    parsed = json.loads(event[len("data: "):].strip())
                    accumulated_tokens += parsed.get("token", "")
                except Exception:
                    pass
                yield event

        # Persist the full conversation exchange to DB after streaming finishes
        with db_session_module.SessionLocal() as session:
            try:
                citations_data = done_payload.get("citations", [])
                answer = done_payload.get("answer", accumulated_tokens.strip())

                user_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.USER,
                    content=question,
                )
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=answer,
                    citations=citations_data,
                )
                session.add(user_msg)
                session.add(assistant_msg)
                session.flush()

                session.add(
                    QueryLog(
                        user_id=user_id,
                        conversation_id=conversation_id,
                        message_id=assistant_msg.id,
                        question=question,
                        topic=extract_topic(question),
                        provider=done_payload.get("provider", ""),
                        citation_count=len(citations_data),
                        insufficient_information=done_payload.get("insufficient_information", False),
                    )
                )

                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv and conv.title == "New Conversation":
                    conv.title = _conversation_title(question)

                session.commit()

                # Send the conversation_id and message_id back so the frontend can link up
                meta_event = {
                    "conversation_id": conversation_id,
                    "message_id": assistant_msg.id,
                }
                yield f"data: [META] {json.dumps(meta_event)}\n\n"
            except Exception as ex:
                logger.error("Failed to persist conversation messages: %s", ex, exc_info=True)
                session.rollback()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
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
