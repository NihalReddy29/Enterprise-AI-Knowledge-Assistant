"""Organization REST endpoints."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import joinedload

from app.models.user import Document, OrgInvite, Organization, OrgMember, OrgRole, User, UserRole
from app.schemas.org import (
    InviteRequest,
    InviteResponse,
    OrgCreate,
    OrgDetail,
    OrgMemberResponse,
    OrgResponse,
)
from app.utils.dependencies import CurrentUser, DbSession
from app.utils.sanitizer import sanitize_text

router = APIRouter(prefix="/orgs", tags=["Organizations"])


def _generate_slug(db: DbSession, name: str) -> str:
    """Create a unique URL slug from org name."""
    base_slug = sanitize_text(name).lower().replace(" ", "-")
    # Clean non-alphanumeric chars except dashes
    base_slug = "".join(c for c in base_slug if c.isalnum() or c == "-").strip("-")
    if not base_slug:
        base_slug = "org"

    slug = base_slug
    counter = 1
    while db.query(Organization).filter(Organization.slug == slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _get_org_membership(db: DbSession, org_id: int, user_id: int) -> OrgMember | None:
    return (
        db.query(OrgMember)
        .filter(OrgMember.org_id == org_id, OrgMember.user_id == user_id)
        .first()
    )


def _require_org_role(
    db: DbSession, org_id: int, user: User, allowed_roles: list[OrgRole]
) -> OrgMember:
    if user.role == UserRole.ADMIN:
        # App admins get owner-level access
        membership = _get_org_membership(db, org_id, user.id)
        if not membership:
            membership = OrgMember(
                org_id=org_id, user_id=user.id, role=OrgRole.OWNER
            )
        return membership

    membership = _get_org_membership(db, org_id, user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization",
        )
    if membership.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient organization permissions",
        )
    return membership


@router.post(
    "",
    response_model=OrgResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization",
)
def create_org(
    payload: OrgCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OrgResponse:
    """Create an organization and make current user owner."""
    slug = _generate_slug(db, payload.name)
    org = Organization(
        name=payload.name,
        slug=slug,
        created_by=current_user.id,
    )
    db.add(org)
    db.flush()

    member = OrgMember(
        org_id=org.id,
        user_id=current_user.id,
        role=OrgRole.OWNER,
    )
    db.add(member)
    db.commit()
    db.refresh(org)

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_by=org.created_by,
        created_at=org.created_at,
        member_count=1,
        my_role=OrgRole.OWNER,
    )


@router.get(
    "",
    response_model=list[OrgResponse],
    summary="List user's organizations",
)
def list_orgs(
    db: DbSession,
    current_user: CurrentUser,
) -> list[OrgResponse]:
    """List all organizations current user belongs to (or all if app admin)."""
    if current_user.role == UserRole.ADMIN:
        orgs = db.query(Organization).order_by(Organization.created_at.desc()).all()
    else:
        memberships = (
            db.query(OrgMember)
            .filter(OrgMember.user_id == current_user.id)
            .all()
        )
        org_ids = [m.org_id for m in memberships]
        orgs = (
            db.query(Organization)
            .filter(Organization.id.in_(org_ids))
            .order_by(Organization.created_at.desc())
            .all()
        )

    result: list[OrgResponse] = []
    for org in orgs:
        member_count = db.query(OrgMember).filter(OrgMember.org_id == org.id).count()
        my_mem = _get_org_membership(db, org.id, current_user.id)
        my_role = my_mem.role if my_mem else (OrgRole.OWNER if current_user.role == UserRole.ADMIN else None)
        result.append(
            OrgResponse(
                id=org.id,
                name=org.name,
                slug=org.slug,
                created_by=org.created_by,
                created_at=org.created_at,
                member_count=member_count,
                my_role=my_role,
            )
        )
    return result


@router.get(
    "/{org_id}",
    response_model=OrgDetail,
    summary="Get organization details with members",
)
def get_org(
    org_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OrgDetail:
    """Get org detail including member list."""
    org = (
        db.query(Organization)
        .options(joinedload(Organization.members).joinedload(OrgMember.user))
        .filter(Organization.id == org_id)
        .first()
    )
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")

    _require_org_role(db, org_id, current_user, [OrgRole.OWNER, OrgRole.ADMIN, OrgRole.MEMBER])

    members_resp = [
        OrgMemberResponse(
            id=m.id,
            org_id=m.org_id,
            user_id=m.user_id,
            role=m.role,
            joined_at=m.joined_at,
            user_email=m.user.email if m.user else None,
            user_name=m.user.name if m.user else None,
        )
        for m in org.members
    ]

    my_mem = _get_org_membership(db, org.id, current_user.id)
    my_role = my_mem.role if my_mem else (OrgRole.OWNER if current_user.role == UserRole.ADMIN else None)

    return OrgDetail(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_by=org.created_by,
        created_at=org.created_at,
        member_count=len(members_resp),
        my_role=my_role,
        members=members_resp,
    )


@router.post(
    "/{org_id}/invite",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a member by email",
)
def invite_member(
    org_id: int,
    payload: InviteRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> InviteResponse:
    """Generate an invitation link for an email address."""
    _require_org_role(db, org_id, current_user, [OrgRole.OWNER, OrgRole.ADMIN])

    # Check if target user is already a member
    target_user = db.query(User).filter(User.email == payload.email).first()
    if target_user:
        existing_mem = _get_org_membership(db, org_id, target_user.id)
        if existing_mem:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this organization",
            )

    token = str(uuid.uuid4())
    invite = OrgInvite(
        org_id=org_id,
        email=payload.email,
        token=token,
        role=payload.role,
        invited_by=current_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)

    invite_url = f"/orgs/invites/{token}/accept"
    return InviteResponse(
        id=invite.id,
        org_id=invite.org_id,
        email=invite.email,
        role=invite.role,
        token=invite.token,
        invite_url=invite_url,
        created_at=invite.created_at,
    )


@router.post(
    "/invites/{token}/accept",
    response_model=OrgResponse,
    summary="Accept an invitation token",
)
def accept_invite(
    token: str,
    db: DbSession,
    current_user: CurrentUser,
) -> OrgResponse:
    """Accept an org invite using its token."""
    invite = db.query(OrgInvite).filter(OrgInvite.token == token).first()
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid invite link")

    if invite.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invite link already used"
        )

    if invite.expires_at:
        expires_at = invite.expires_at
        now = datetime.now(timezone.utc).replace(tzinfo=None) if expires_at.tzinfo is None else datetime.now(timezone.utc)
        if expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invite link has expired"
            )



    existing_mem = _get_org_membership(db, invite.org_id, current_user.id)
    if not existing_mem:
        mem = OrgMember(
            org_id=invite.org_id,
            user_id=current_user.id,
            role=invite.role,
        )
        db.add(mem)

    invite.accepted_at = datetime.now(timezone.utc)
    db.commit()

    org = db.query(Organization).filter(Organization.id == invite.org_id).first()
    member_count = db.query(OrgMember).filter(OrgMember.org_id == org.id).count()

    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        created_by=org.created_by,
        created_at=org.created_at,
        member_count=member_count,
        my_role=invite.role,
    )


@router.delete(
    "/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from an organization",
)
def remove_member(
    org_id: int,
    user_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Remove a user from org (owner/admin only, or user leaving themselves)."""
    if user_id != current_user.id:
        _require_org_role(db, org_id, current_user, [OrgRole.OWNER, OrgRole.ADMIN])

    membership = _get_org_membership(db, org_id, user_id)
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if membership.role == OrgRole.OWNER and user_id == current_user.id:
        owner_count = (
            db.query(OrgMember)
            .filter(OrgMember.org_id == org_id, OrgMember.role == OrgRole.OWNER)
            .count()
        )
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot leave organization as sole owner. Transfer ownership first or delete organization.",
            )

    db.delete(membership)
    db.commit()
