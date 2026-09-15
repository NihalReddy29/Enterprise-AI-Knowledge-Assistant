"""Team-scoped RAG chat endpoints."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload

from app.models.team import Team, TeamChatMessage, TeamConversation
from app.schemas.chat import CitationSchema
from app.schemas.team import (
    TeamChatMessageOut,
    TeamChatQueryRequest,
    TeamChatQueryResponse,
    TeamConversationDetailOut,
    TeamConversationOut,
)
from app.services.rag import get_rag_service
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.sanitizer import sanitize_text
from app.utils.team_dependencies import get_team_membership_row, get_team_or_404

router = APIRouter(prefix="/teams", tags=["Team Chat"])


def _conversation_title(question: str) -> str:
    cleaned = " ".join(question.strip().split())
    return cleaned[:80] if cleaned else "New Conversation"


def _get_team_conversation(
    db: DbSession, team_id: int, conversation_id: int
) -> TeamConversation:
    conversation = (
        db.query(TeamConversation)
        .options(joinedload(TeamConversation.messages))
        .filter(
            TeamConversation.id == conversation_id,
            TeamConversation.team_id == team_id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


@router.post(
    "/{team_id}/chat",
    response_model=TeamChatQueryResponse,
    summary="Ask a question against the team knowledge base",
)
async def team_chat_query(
    team_id: int,
    payload: TeamChatQueryRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamChatQueryResponse:
    """RAG chat scoped exclusively to the team's documents and vector collection."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )
    team = get_team_or_404(db, team_id)
    question = sanitize_text(payload.question, max_length=4000)

    if payload.conversation_id:
        conversation = _get_team_conversation(db, team_id, payload.conversation_id)
    else:
        conversation = TeamConversation(team_id=team_id, title=_conversation_title(question))
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = [
        {"role": msg.role, "content": msg.content}
        for msg in conversation.messages
    ]

    rag = get_rag_service()
    result = rag.ask(
        question=question,
        owner_id=None,
        document_ids=payload.document_ids,
        top_k=payload.top_k,
        chat_history=history,
        team_id=team_id,
        collection_name=team.qdrant_collection_name,
    )

    citations_data = [c.to_dict() for c in result.citations]

    user_message = TeamChatMessage(
        team_id=team_id,
        conversation_id=conversation.id,
        user_id=current_user.id,
        role="user",
        content=question,
    )
    assistant_message = TeamChatMessage(
        team_id=team_id,
        conversation_id=conversation.id,
        user_id=None,
        role="assistant",
        content=result.answer,
        citations=citations_data,
    )
    db.add(user_message)
    db.add(assistant_message)

    if conversation.title == "New Conversation":
        conversation.title = _conversation_title(question)

    db.commit()
    db.refresh(assistant_message)

    return TeamChatQueryResponse(
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
    "/{team_id}/conversations",
    response_model=list[TeamConversationOut],
    summary="List team RAG conversations",
)
def list_team_conversations(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TeamConversationOut]:
    """List shared RAG conversations for a team."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    conversations = (
        db.query(TeamConversation)
        .filter(TeamConversation.team_id == team_id)
        .order_by(TeamConversation.created_at.desc())
        .all()
    )
    return [TeamConversationOut.model_validate(c) for c in conversations]


@router.get(
    "/{team_id}/conversations/{conversation_id}",
    response_model=TeamConversationDetailOut,
    summary="Get team conversation with messages",
)
def get_team_conversation(
    team_id: int,
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamConversationDetailOut:
    """Get a team conversation and its messages."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    conversation = (
        db.query(TeamConversation)
        .options(
            joinedload(TeamConversation.messages).joinedload(TeamChatMessage.author)
        )
        .filter(
            TeamConversation.id == conversation_id,
            TeamConversation.team_id == team_id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = [
        TeamChatMessageOut(
            id=m.id,
            team_id=m.team_id,
            conversation_id=m.conversation_id,
            user_id=m.user_id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            created_at=m.created_at,
            author_name=m.author.name if m.author else None,
        )
        for m in conversation.messages
    ]

    return TeamConversationDetailOut(
        id=conversation.id,
        team_id=conversation.team_id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=messages,
    )
