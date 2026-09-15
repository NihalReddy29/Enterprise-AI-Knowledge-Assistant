"""Team messenger REST + WebSocket endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import joinedload

from app.database.session import SessionLocal
from app.models.team import (
    MessengerMessageType,
    TeamMessengerMessage,
    TeamMessengerRead,
)
from app.models.user import User
from app.schemas.team import (
    TeamMessengerMessageCreate,
    TeamMessengerMessageListResponse,
    TeamMessengerMessageOut,
)
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.security import decode_access_token
from app.utils.team_dependencies import get_team_membership_row, get_team_or_404
from app.ws.team_messenger import messenger_manager

router = APIRouter(prefix="/teams", tags=["Team Messenger"])
ws_router = APIRouter(tags=["Team Messenger WebSocket"])


def _message_out(message: TeamMessengerMessage) -> TeamMessengerMessageOut:
    read_ids = [r.user_id for r in message.reads] if message.reads else []
    return TeamMessengerMessageOut(
        id=message.id,
        team_id=message.team_id,
        sender_id=message.sender_id,
        content=message.content,
        message_type=message.message_type,
        file_document_id=message.file_document_id,
        reply_to_id=message.reply_to_id,
        created_at=message.created_at,
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        sender_name=message.sender.name if message.sender else None,
        read_by_user_ids=read_ids,
    )


def _authenticate_ws_token(token: str | None) -> User | None:
    if not token:
        return None
    token_data = decode_access_token(token)
    if not token_data:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.email == token_data.sub).first()
    finally:
        db.close()


@ws_router.websocket("/ws/teams/{team_id}/messenger")
async def team_messenger_ws(websocket: WebSocket, team_id: int, token: str | None = Query(None)):
    """Real-time team messenger. Authenticate via ?token=<jwt>."""
    user = _authenticate_ws_token(token)
    if not user:
        await websocket.close(code=4401)
        return

    db = SessionLocal()
    try:
        membership = get_team_membership_row(db, team_id, user.id)
        if not membership:
            await websocket.close(code=4403)
            return
    finally:
        db.close()

    await messenger_manager.connect(team_id, user.id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            db = SessionLocal()
            try:
                membership = get_team_membership_row(db, team_id, user.id)
                if not membership:
                    break

                import json

                data = json.loads(raw)
                content = (data.get("content") or "").strip()
                if not content:
                    continue

                message_type = MessengerMessageType.TEXT
                if data.get("message_type") == "file":
                    message_type = MessengerMessageType.FILE

                message = TeamMessengerMessage(
                    team_id=team_id,
                    sender_id=user.id,
                    content=content,
                    message_type=message_type,
                    file_document_id=data.get("file_document_id"),
                    reply_to_id=data.get("reply_to_id"),
                )
                db.add(message)
                db.commit()
                db.refresh(message)
                message = (
                    db.query(TeamMessengerMessage)
                    .options(joinedload(TeamMessengerMessage.sender))
                    .filter(TeamMessengerMessage.id == message.id)
                    .first()
                )
                payload = {
                    "type": "message",
                    "message": _message_out(message).model_dump(mode="json"),
                }
            finally:
                db.close()

            await messenger_manager.broadcast(team_id, payload)
    except WebSocketDisconnect:
        pass
    finally:
        messenger_manager.disconnect(team_id, user.id)


@router.get(
    "/{team_id}/messages",
    response_model=TeamMessengerMessageListResponse,
    summary="Paginated team messenger history",
)
def list_messages(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
    before: int | None = Query(default=None, description="Load messages before this message ID"),
    limit: int = Query(default=50, ge=1, le=100),
) -> TeamMessengerMessageListResponse:
    """Load messenger history for infinite scroll."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    query = (
        db.query(TeamMessengerMessage)
        .options(
            joinedload(TeamMessengerMessage.sender),
            joinedload(TeamMessengerMessage.reads),
        )
        .filter(
            TeamMessengerMessage.team_id == team_id,
            TeamMessengerMessage.deleted_at.is_(None),
        )
    )
    if before is not None:
        anchor = db.query(TeamMessengerMessage).filter(TeamMessengerMessage.id == before).first()
        if anchor:
            query = query.filter(TeamMessengerMessage.created_at < anchor.created_at)

    total = (
        db.query(TeamMessengerMessage)
        .filter(
            TeamMessengerMessage.team_id == team_id,
            TeamMessengerMessage.deleted_at.is_(None),
        )
        .count()
    )
    messages = (
        query.order_by(TeamMessengerMessage.created_at.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(messages) > limit
    messages = messages[:limit]
    messages.reverse()

    return TeamMessengerMessageListResponse(
        messages=[_message_out(m) for m in messages],
        total=total,
        has_more=has_more,
    )


@router.post(
    "/{team_id}/messages",
    response_model=TeamMessengerMessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Send a team messenger message (HTTP fallback)",
)
def send_message(
    team_id: int,
    payload: TeamMessengerMessageCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamMessengerMessageOut:
    """Send a message via HTTP (also broadcast to WebSocket clients)."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )
    get_team_or_404(db, team_id)

    message = TeamMessengerMessage(
        team_id=team_id,
        sender_id=current_user.id,
        content=payload.content,
        message_type=payload.message_type,
        file_document_id=payload.file_document_id,
        reply_to_id=payload.reply_to_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    message = (
        db.query(TeamMessengerMessage)
        .options(joinedload(TeamMessengerMessage.sender))
        .filter(TeamMessengerMessage.id == message.id)
        .first()
    )

    import asyncio

    out = _message_out(message)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(
                messenger_manager.broadcast(
                    team_id,
                    {"type": "message", "message": out.model_dump(mode="json")},
                )
            )
    except RuntimeError:
        pass

    return out


@router.post(
    "/{team_id}/messages/{message_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark a messenger message as read",
)
async def mark_message_read(
    team_id: int,
    message_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Record a read receipt and broadcast to connected clients."""
    if not get_team_membership_row(db, team_id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    message = (
        db.query(TeamMessengerMessage)
        .filter(
            TeamMessengerMessage.id == message_id,
            TeamMessengerMessage.team_id == team_id,
        )
        .first()
    )
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    existing = (
        db.query(TeamMessengerRead)
        .filter(
            TeamMessengerRead.message_id == message_id,
            TeamMessengerRead.user_id == current_user.id,
        )
        .first()
    )
    if not existing:
        db.add(
            TeamMessengerRead(
                message_id=message_id,
                user_id=current_user.id,
                read_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        await messenger_manager.broadcast(
            team_id,
            {
                "type": "read",
                "message_id": message_id,
                "user_id": current_user.id,
                "read_at": datetime.now(timezone.utc).isoformat(),
            },
        )
