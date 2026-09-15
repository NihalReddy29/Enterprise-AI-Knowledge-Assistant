"""FastAPI dependencies for team-scoped authorization."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.team import Team, TeamMember, TeamMemberRole, TeamMemberStatus
from app.models.user import User
from app.utils.dependencies import get_current_user

ADMIN_ROLES = {TeamMemberRole.OWNER, TeamMemberRole.ADMIN}


def get_team_or_404(db: Session, team_id: int) -> Team:
    """Return the team or raise 404."""
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def get_team_membership_row(
    db: Session, team_id: int, user_id: int
) -> TeamMember | None:
    """Return active membership row if it exists."""
    return (
        db.query(TeamMember)
        .filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.status == TeamMemberStatus.ACTIVE,
        )
        .first()
    )


def get_team_membership(
    team_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamMember:
    """Require active team membership; return the membership row."""
    get_team_or_404(db, team_id)
    membership = get_team_membership_row(db, team_id, current_user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not an active member of this team",
        )
    return membership


def require_team_admin(
    team_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamMember:
    """Require owner or admin role on the team."""
    membership = get_team_membership(team_id, db, current_user)
    if membership.role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team admin permissions required",
        )
    return membership


def require_team_owner(
    team_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TeamMember:
    """Require team owner role."""
    membership = get_team_membership(team_id, db, current_user)
    if membership.role != TeamMemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team owner permissions required",
        )
    return membership


TeamMembership = Annotated[TeamMember, Depends(get_team_membership)]
TeamAdmin = Annotated[TeamMember, Depends(require_team_admin)]
TeamOwner = Annotated[TeamMember, Depends(require_team_owner)]
