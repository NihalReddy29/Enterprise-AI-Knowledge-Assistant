"""Team workspace REST endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import joinedload

from app.config import get_settings
from app.models.team import (
    Notification,
    Team,
    TeamInvite,
    TeamInviteStatus,
    TeamJoinRequest,
    TeamJoinRequestStatus,
    TeamMember,
    TeamMemberRole,
    TeamMemberStatus,
)
from app.models.user import User
from app.schemas.team import (
    TeamCreate,
    TeamDetail,
    TeamInviteCreate,
    TeamInviteListResponse,
    TeamInviteOut,
    TeamInvitePreview,
    TeamJoinCodePreview,
    TeamJoinRequestCreate,
    TeamJoinRequestListResponse,
    TeamJoinRequestOut,
    TeamMemberOut,
    TeamOut,
    TeamUpdate,
)
from app.services.email import send_team_invite_email
from app.services.team_collections import delete_team_collection, ensure_team_collection
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.team_dependencies import (
    ADMIN_ROLES,
    get_team_membership_row,
    get_team_or_404,
    require_team_admin,
    require_team_owner,
)
from app.utils.team_join_codes import generate_join_code, normalize_join_code

router = APIRouter(prefix="/teams", tags=["Teams"])


def _team_collection_name(team_id: int) -> str:
    return f"team_{team_id}"


def _build_team_out(db: DbSession, team: Team, current_user: CurrentUser) -> TeamOut:
    member_count = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team.id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .count()
    )
    membership = get_team_membership_row(db, team.id, current_user.id)
    return TeamOut(
        id=team.id,
        name=team.name,
        description=team.description,
        owner_id=team.owner_id,
        qdrant_collection_name=team.qdrant_collection_name,
        created_at=team.created_at,
        updated_at=team.updated_at,
        member_count=member_count,
        my_role=membership.role if membership else None,
    )


def _build_member_out(member: TeamMember) -> TeamMemberOut:
    return TeamMemberOut(
        id=member.id,
        team_id=member.team_id,
        user_id=member.user_id,
        role=member.role,
        status=member.status,
        joined_at=member.joined_at,
        user_email=member.user.email if member.user else None,
        user_name=member.user.name if member.user else None,
    )


@router.post(
    "",
    response_model=TeamOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new team",
)
def create_team(
    payload: TeamCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamOut:
    """Create a team; the creator becomes owner with an isolated vector collection."""
    placeholder_collection = f"team_pending_{current_user.id}"
    team = Team(
        name=payload.name,
        description=payload.description,
        owner_id=current_user.id,
        qdrant_collection_name=placeholder_collection,
        join_code=generate_join_code(db),
    )
    db.add(team)
    db.flush()

    team.qdrant_collection_name = _team_collection_name(team.id)
    member = TeamMember(
        team_id=team.id,
        user_id=current_user.id,
        role=TeamMemberRole.OWNER,
        status=TeamMemberStatus.ACTIVE,
    )
    db.add(member)
    db.commit()
    db.refresh(team)

    ensure_team_collection(team)

    return _build_team_out(db, team, current_user)


@router.get(
    "",
    response_model=list[TeamOut],
    summary="List teams the current user belongs to",
)
def list_teams(
    db: DbSession,
    current_user: CurrentUser,
) -> list[TeamOut]:
    """List all teams where the user has active membership."""
    memberships = (
        db.query(TeamMember)
        .filter(
            TeamMember.user_id == current_user.id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .all()
    )
    team_ids = [m.team_id for m in memberships]
    if not team_ids:
        return []

    teams = (
        db.query(Team)
        .filter(Team.id.in_(team_ids))
        .order_by(Team.created_at.desc())
        .all()
    )
    return [_build_team_out(db, team, current_user) for team in teams]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _expire_invite_if_needed(invite: TeamInvite, db: DbSession) -> TeamInvite:
    """Mark invite expired when past expires_at."""
    if invite.status != TeamInviteStatus.PENDING:
        return invite
    expires_at = _normalize_dt(invite.expires_at)
    if expires_at and expires_at < _utcnow():
        invite.status = TeamInviteStatus.EXPIRED
        db.commit()
        db.refresh(invite)
    return invite


def _invite_url(token: str) -> str:
    settings = get_settings()
    return f"{settings.frontend_url.rstrip('/')}/invites/{token}"


def _build_invite_out(invite: TeamInvite) -> TeamInviteOut:
    return TeamInviteOut(
        id=invite.id,
        team_id=invite.team_id,
        invited_email=invite.invited_email,
        invited_by=invite.invited_by,
        token=invite.token,
        status=invite.status,
        created_at=invite.created_at,
        responded_at=invite.responded_at,
        expires_at=invite.expires_at,
        invite_url=_invite_url(invite.token),
    )


@router.get(
    "/invites/pending",
    response_model=TeamInviteListResponse,
    summary="List pending invites for the current user",
)
def list_pending_invites(
    db: DbSession,
    current_user: CurrentUser,
) -> TeamInviteListResponse:
    """Return pending team invites addressed to the logged-in user's email."""
    email = current_user.email.lower()
    invites = (
        db.query(TeamInvite)
        .filter(
            TeamInvite.invited_email == email,
            TeamInvite.status == TeamInviteStatus.PENDING,
        )
        .order_by(TeamInvite.created_at.desc())
        .all()
    )
    active_invites: list[TeamInvite] = []
    for invite in invites:
        invite = _expire_invite_if_needed(invite, db)
        if invite.status == TeamInviteStatus.PENDING:
            active_invites.append(invite)

    items = [_build_invite_out(i) for i in active_invites]
    return TeamInviteListResponse(invites=items, total=len(items))


@router.get(
    "/invites/{token}",
    response_model=TeamInvitePreview,
    summary="Preview a team invite by token",
)
def preview_invite(
    token: str,
    db: DbSession,
) -> TeamInvitePreview:
    """Public preview of an invite (token is the credential)."""
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")

    invite = _expire_invite_if_needed(invite, db)
    team = get_team_or_404(db, invite.team_id)
    inviter = (
        db.query(User).filter(User.id == invite.invited_by).first()
        if invite.invited_by
        else None
    )

    return TeamInvitePreview(
        team_name=team.name,
        team_description=team.description,
        inviter_name=inviter.name if inviter else None,
        inviter_email=inviter.email if inviter else None,
        status=invite.status,
        expires_at=invite.expires_at,
    )


@router.post(
    "/invites/{token}/accept",
    response_model=TeamOut,
    summary="Accept a team invite",
)
def accept_invite(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamOut:
    """Accept an invite; creates active team membership."""
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")

    invite = _expire_invite_if_needed(invite, db)
    if invite.status != TeamInviteStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invite is no longer pending ({invite.status.value})",
        )

    if current_user.email.lower() != invite.invited_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invite was sent to a different email address",
        )

    existing = get_team_membership_row(db, invite.team_id, current_user.id)
    if not existing:
        db.add(
            TeamMember(
                team_id=invite.team_id,
                user_id=current_user.id,
                role=TeamMemberRole.MEMBER,
                status=TeamMemberStatus.ACTIVE,
            )
        )

    invite.status = TeamInviteStatus.ACCEPTED
    invite.responded_at = _utcnow()
    db.commit()

    team = get_team_or_404(db, invite.team_id)
    return _build_team_out(db, team, current_user)


def _build_join_request_out(request: TeamJoinRequest) -> TeamJoinRequestOut:
    return TeamJoinRequestOut(
        id=request.id,
        team_id=request.team_id,
        user_id=request.user_id,
        status=request.status,
        message=request.message,
        reviewed_by=request.reviewed_by,
        created_at=request.created_at,
        responded_at=request.responded_at,
        user_email=request.user.email if request.user else None,
        user_name=request.user.name if request.user else None,
    )


def _notify_team_admins(
    db: DbSession,
    team_id: int,
    *,
    notification_type: str,
    title: str,
    body: str,
    payload: dict,
) -> None:
    admins = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
            TeamMember.role.in_(ADMIN_ROLES),
        )
        .all()
    )
    for admin in admins:
        db.add(
            Notification(
                user_id=admin.user_id,
                type=notification_type,
                title=title,
                body=body,
                payload=payload,
            )
        )


@router.get(
    "/join/preview",
    response_model=TeamJoinCodePreview,
    summary="Preview a team by join code",
)
def preview_join_code(
    code: str,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamJoinCodePreview:
    """Look up a team by its public join code before requesting membership."""
    try:
        normalized = normalize_join_code(code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    team = db.query(Team).filter(Team.join_code == normalized).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid join code")

    membership = get_team_membership_row(db, team.id, current_user.id)
    if membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this team",
        )

    member_count = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team.id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .count()
    )
    return TeamJoinCodePreview(
        team_id=team.id,
        team_name=team.name,
        team_description=team.description,
        member_count=member_count,
    )


@router.post(
    "/join",
    response_model=TeamJoinRequestOut,
    status_code=status.HTTP_201_CREATED,
    summary="Request to join a team by code",
)
def request_join_team(
    payload: TeamJoinRequestCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamJoinRequestOut:
    """Submit a join request; team admins must approve before membership is granted."""
    try:
        normalized = normalize_join_code(payload.join_code)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    team = db.query(Team).filter(Team.join_code == normalized).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid join code")

    membership = get_team_membership_row(db, team.id, current_user.id)
    if membership:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already a member of this team",
        )

    existing_request = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.user))
        .filter(
            TeamJoinRequest.team_id == team.id,
            TeamJoinRequest.user_id == current_user.id,
        )
        .first()
    )

    if existing_request:
        if existing_request.status == TeamJoinRequestStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You already have a pending join request for this team",
            )
        if existing_request.status == TeamJoinRequestStatus.APPROVED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You have already been approved for this team",
            )
        existing_request.status = TeamJoinRequestStatus.PENDING
        existing_request.message = payload.message
        existing_request.reviewed_by = None
        existing_request.responded_at = None
        join_request = existing_request
    else:
        join_request = TeamJoinRequest(
            team_id=team.id,
            user_id=current_user.id,
            message=payload.message,
            status=TeamJoinRequestStatus.PENDING,
        )
        db.add(join_request)

    db.flush()
    _notify_team_admins(
        db,
        team.id,
        notification_type="team_join_request",
        title=f"Join request for {team.name}",
        body=f"{current_user.name} requested to join your team.",
        payload={"team_id": team.id, "join_request_id": join_request.id},
    )
    db.commit()
    db.refresh(join_request)

    join_request = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.user))
        .filter(TeamJoinRequest.id == join_request.id)
        .first()
    )
    return _build_join_request_out(join_request)


@router.post(
    "/invites/{token}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject a team invite",
)
def reject_invite(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Reject an invite without creating membership."""
    invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")

    invite = _expire_invite_if_needed(invite, db)
    if invite.status != TeamInviteStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invite is no longer pending ({invite.status.value})",
        )

    if current_user.email.lower() != invite.invited_email.lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This invite was sent to a different email address",
        )

    invite.status = TeamInviteStatus.REJECTED
    invite.responded_at = _utcnow()
    db.commit()


@router.post(
    "/{team_id}/invites",
    response_model=TeamInviteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member by email",
)
def create_invite(
    team_id: int,
    payload: TeamInviteCreate,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamInviteOut:
    """Create a team invite and email the invitee (admin-only)."""
    require_team_admin(team_id, db, current_user)
    team = get_team_or_404(db, team_id)
    email = payload.email

    target_user = db.query(User).filter(User.email == email).first()
    if target_user:
        existing = get_team_membership_row(db, team_id, target_user.id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this team",
            )

    pending = (
        db.query(TeamInvite)
        .filter(
            TeamInvite.team_id == team_id,
            TeamInvite.invited_email == email,
            TeamInvite.status == TeamInviteStatus.PENDING,
        )
        .first()
    )
    if pending:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A pending invite already exists for this email",
        )

    settings = get_settings()
    token = str(uuid.uuid4())
    invite = TeamInvite(
        team_id=team_id,
        invited_email=email,
        invited_by=current_user.id,
        token=token,
        status=TeamInviteStatus.PENDING,
        expires_at=_utcnow() + timedelta(days=settings.team_invite_expire_days),
    )
    db.add(invite)

    if target_user:
        db.add(
            Notification(
                user_id=target_user.id,
                type="team_invite",
                title=f"Invitation to join {team.name}",
                body=f"{current_user.name} invited you to join the team \"{team.name}\".",
                payload={"team_id": team_id, "invite_token": token},
            )
        )

    db.commit()
    db.refresh(invite)

    invite_url = _invite_url(token)
    background_tasks.add_task(
        send_team_invite_email,
        email,
        team.name,
        current_user.name,
        invite_url,
    )

    return _build_invite_out(invite)


@router.get(
    "/{team_id}",
    response_model=TeamDetail,
    summary="Get team details",
)
def get_team(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamDetail:
    """Get team detail including members (active members only)."""
    team = (
        db.query(Team)
        .options(joinedload(Team.members).joinedload(TeamMember.user))
        .filter(Team.id == team_id)
        .first()
    )
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")

    membership = get_team_membership_row(db, team_id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    active_members = [m for m in team.members if m.status == TeamMemberStatus.ACTIVE]
    pending_join_count = (
        db.query(TeamJoinRequest)
        .filter(
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == TeamJoinRequestStatus.PENDING,
        )
        .count()
    )
    base = _build_team_out(db, team, current_user)
    return TeamDetail(
        **base.model_dump(),
        members=[_build_member_out(m) for m in active_members],
        join_code=team.join_code if membership.role in ADMIN_ROLES else None,
        pending_join_request_count=pending_join_count if membership.role in ADMIN_ROLES else 0,
    )


@router.patch(
    "/{team_id}",
    response_model=TeamOut,
    summary="Update team name or description",
)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamOut:
    """Update team metadata (admin-only)."""
    require_team_admin(team_id, db, current_user)
    team = get_team_or_404(db, team_id)

    if payload.name is not None:
        team.name = payload.name
    if payload.description is not None:
        team.description = payload.description

    db.commit()
    db.refresh(team)
    return _build_team_out(db, team, current_user)


@router.delete(
    "/{team_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a team",
)
def delete_team(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a team and cascade all related data (owner-only)."""
    require_team_owner(team_id, db, current_user)
    team = get_team_or_404(db, team_id)
    delete_team_collection(team)
    db.delete(team)
    db.commit()


@router.post(
    "/{team_id}/join-code/regenerate",
    response_model=TeamOut,
    summary="Regenerate team join code",
)
def regenerate_join_code(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamOut:
    """Generate a new join code (admin-only). Invalidates the previous code."""
    require_team_admin(team_id, db, current_user)
    team = get_team_or_404(db, team_id)
    team.join_code = generate_join_code(db)
    db.commit()
    db.refresh(team)
    return _build_team_out(db, team, current_user)


@router.get(
    "/{team_id}/join-requests",
    response_model=TeamJoinRequestListResponse,
    summary="List pending join requests",
)
def list_join_requests(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamJoinRequestListResponse:
    """List users waiting for approval to join (admin-only)."""
    require_team_admin(team_id, db, current_user)
    requests = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.user))
        .filter(
            TeamJoinRequest.team_id == team_id,
            TeamJoinRequest.status == TeamJoinRequestStatus.PENDING,
        )
        .order_by(TeamJoinRequest.created_at.asc())
        .all()
    )
    items = [_build_join_request_out(r) for r in requests]
    return TeamJoinRequestListResponse(requests=items, total=len(items))


@router.post(
    "/{team_id}/join-requests/{request_id}/approve",
    response_model=TeamMemberOut,
    summary="Approve a join request",
)
def approve_join_request(
    team_id: int,
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> TeamMemberOut:
    """Approve a pending join request and add the user as a member (admin-only)."""
    require_team_admin(team_id, db, current_user)
    team = get_team_or_404(db, team_id)

    join_request = (
        db.query(TeamJoinRequest)
        .options(joinedload(TeamJoinRequest.user))
        .filter(
            TeamJoinRequest.id == request_id,
            TeamJoinRequest.team_id == team_id,
        )
        .first()
    )
    if not join_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")
    if join_request.status != TeamJoinRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Join request is not pending ({join_request.status.value})",
        )

    membership = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == join_request.user_id,
        )
        .first()
    )
    if membership and membership.status == TeamMemberStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already an active member",
        )

    if membership:
        membership.status = TeamMemberStatus.ACTIVE
        membership.role = TeamMemberRole.MEMBER
        member = membership
    else:
        member = TeamMember(
            team_id=team_id,
            user_id=join_request.user_id,
            role=TeamMemberRole.MEMBER,
            status=TeamMemberStatus.ACTIVE,
        )
        db.add(member)

    join_request.status = TeamJoinRequestStatus.APPROVED
    join_request.reviewed_by = current_user.id
    join_request.responded_at = _utcnow()

    db.add(
        Notification(
            user_id=join_request.user_id,
            type="team_join_approved",
            title=f"Welcome to {team.name}",
            body=f"Your request to join {team.name} was approved.",
            payload={"team_id": team_id},
        )
    )
    db.commit()
    db.refresh(member)

    member = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .filter(TeamMember.id == member.id)
        .first()
    )
    return _build_member_out(member)


@router.post(
    "/{team_id}/join-requests/{request_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reject a join request",
)
def reject_join_request(
    team_id: int,
    request_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Reject a pending join request (admin-only)."""
    require_team_admin(team_id, db, current_user)
    team = get_team_or_404(db, team_id)

    join_request = (
        db.query(TeamJoinRequest)
        .filter(
            TeamJoinRequest.id == request_id,
            TeamJoinRequest.team_id == team_id,
        )
        .first()
    )
    if not join_request:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Join request not found")
    if join_request.status != TeamJoinRequestStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Join request is not pending ({join_request.status.value})",
        )

    join_request.status = TeamJoinRequestStatus.REJECTED
    join_request.reviewed_by = current_user.id
    join_request.responded_at = _utcnow()

    db.add(
        Notification(
            user_id=join_request.user_id,
            type="team_join_rejected",
            title=f"Join request declined",
            body=f"Your request to join {team.name} was declined.",
            payload={"team_id": team_id},
        )
    )
    db.commit()


@router.get(
    "/{team_id}/members",
    response_model=list[TeamMemberOut],
    summary="List team members",
)
def list_members(
    team_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> list[TeamMemberOut]:
    """List active members of a team."""
    membership = get_team_membership_row(db, team_id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )

    members = (
        db.query(TeamMember)
        .options(joinedload(TeamMember.user))
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .order_by(TeamMember.joined_at.asc())
        .all()
    )
    return [_build_member_out(m) for m in members]


@router.delete(
    "/{team_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a team member",
)
def remove_member(
    team_id: int,
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Remove a member (admin-only; cannot remove the owner)."""
    actor = require_team_admin(team_id, db, current_user)

    target = (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target.role == TeamMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the team owner",
        )

    if actor.role == TeamMemberRole.ADMIN and target.role == TeamMemberRole.ADMIN:
        if user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admins cannot remove other admins",
            )

    target.status = TeamMemberStatus.REMOVED
    db.commit()
