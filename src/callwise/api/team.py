"""Team Management API router: member listing, role updates, member removal, and team invites."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_tenant_db
from callwise.api.permissions import Role, require_manager, require_owner, require_staff
from callwise.api.security import auth_rate_limiter, hash_token
from callwise.config import settings
from callwise.db.models import Business, Invite, Membership, Session as UserSession, User
from callwise.notifications.service import get_email_provider
from callwise.providers.email import EmailMessage

router = APIRouter(prefix="/team", tags=["Team Management"])


# ============================================================================
# Schemas
# ============================================================================

class TeamMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    name: str
    email: str
    role: str
    joined_at: datetime


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., description="Role to assign: owner, manager, or staff")


class InviteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    created_at: datetime


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., description="New role: owner, manager, or staff")


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/members", response_model=List[TeamMemberResponse])
async def list_team_members(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[TeamMemberResponse]:
    """List all team members and their roles for the current business tenant."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(Membership.business_id == business.id)
        .order_by(Membership.created_at.asc())
    )
    memberships = (await db.execute(stmt)).scalars().all()

    return [
        TeamMemberResponse(
            user_id=m.user_id,
            name=m.user.name,
            email=m.user.email,
            role=m.role,
            joined_at=m.created_at,
        )
        for m in memberships
    ]


@router.post("/invites", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_team_member(
    payload: InviteCreateRequest,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_owner),
    db: AsyncSession = Depends(get_tenant_db),
) -> InviteResponse:
    """Send an invitation email with an expiring single-use invite token."""
    user, business, _, _ = auth_ctx

    # Enforce valid role
    target_role = payload.role.lower().strip()
    if target_role not in (Role.OWNER.value, Role.MANAGER.value, Role.STAFF.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: owner, manager, staff.",
        )

    # Rate limiting: max 10 invites per minute per business
    rate_key = f"invite:{business.id}"
    is_limited, retry_after = auth_rate_limiter.is_rate_limited(rate_key, max_attempts=10, window_seconds=60)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many invitations sent recently. Please retry in {retry_after} seconds.",
        )
    auth_rate_limiter.record_attempt(rate_key)

    # Check if user is already an active member of this business
    clean_email = payload.email.lower().strip()
    existing_user_stmt = select(User).where(User.email == clean_email)
    existing_user = (await db.execute(existing_user_stmt)).scalar_one_or_none()

    if existing_user:
        mem_check = select(Membership).where(
            Membership.user_id == existing_user.id,
            Membership.business_id == business.id,
        )
        if (await db.execute(mem_check)).scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"User '{clean_email}' is already a member of this business.",
            )

    # Generate single-use token and hash
    raw_token = uuid.uuid4().hex
    token_hash = hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invite = Invite(
        id=uuid.uuid4(),
        business_id=business.id,
        email=clean_email,
        role=target_role,
        token_hash=token_hash,
        invited_by_user_id=user.id,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()

    # Dispatch email invitation via EmailProvider
    email_prov = get_email_provider()
    invite_url = f"{settings.app_url}/accept-invite?token={raw_token}"
    await email_prov.send_email(
        EmailMessage(
            to=clean_email,
            subject=f"You're invited to join {business.name} on Callwise",
            body_text=(
                f"Hello,\n\n{user.name} has invited you to join '{business.name}' on Callwise "
                f"with the role of {target_role.capitalize()}.\n\n"
                f"Accept your invitation here:\n{invite_url}\n\n"
                f"This link will expire in 7 days."
            ),
        )
    )

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="invite_team_member",
        resource_type="invite",
        resource_id=str(invite.id),
        changes={"email": clean_email, "role": target_role},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return InviteResponse.model_validate(invite)


@router.get("/invites", response_model=List[InviteResponse])
async def list_pending_invites(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[InviteResponse]:
    """List pending unexpired team invitations."""
    _, business, _, _ = auth_ctx
    now = datetime.now(timezone.utc)

    stmt = (
        select(Invite)
        .where(
            Invite.business_id == business.id,
            Invite.expires_at > now,
            Invite.accepted_at.is_(None),
        )
        .order_by(Invite.created_at.desc())
    )
    invites = (await db.execute(stmt)).scalars().all()
    return [InviteResponse.model_validate(inv) for inv in invites]


@router.delete("/invites/{invite_id}")
async def revoke_invite(
    invite_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_owner),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Revoke a pending team invitation."""
    user, business, _, _ = auth_ctx

    stmt = select(Invite).where(Invite.id == invite_id, Invite.business_id == business.id)
    invite = (await db.execute(stmt)).scalar_one_or_none()

    if not invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invite '{invite_id}' not found.",
        )

    await db.delete(invite)
    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="revoke_invite",
        resource_type="invite",
        resource_id=str(invite_id),
        changes={"email": invite.email, "role": invite.role},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"status": "ok", "message": f"Invitation for '{invite.email}' revoked."}


@router.patch("/members/{member_user_id}", response_model=TeamMemberResponse)
async def update_member_role(
    member_user_id: uuid.UUID,
    payload: RoleUpdateRequest,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_owner),
    db: AsyncSession = Depends(get_tenant_db),
) -> TeamMemberResponse:
    """Change a team member's role (enforces at least one owner rule)."""
    user, business, _, _ = auth_ctx

    target_role = payload.role.lower().strip()
    if target_role not in (Role.OWNER.value, Role.MANAGER.value, Role.STAFF.value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: owner, manager, staff.",
        )

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            Membership.user_id == member_user_id,
            Membership.business_id == business.id,
        )
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member '{member_user_id}' not found in this business.",
        )

    # Protect against demoting the last owner
    if membership.role == Role.OWNER.value and target_role != Role.OWNER.value:
        owner_count_stmt = select(func.count(Membership.id)).where(
            Membership.business_id == business.id,
            Membership.role == Role.OWNER.value,
        )
        owner_count = (await db.execute(owner_count_stmt)).scalar() or 0
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the only owner. A business must retain at least one owner.",
            )

    old_role = membership.role
    membership.role = target_role

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="update_member_role",
        resource_type="membership",
        resource_id=str(membership.id),
        changes={"user_email": membership.user.email, "old_role": old_role, "new_role": target_role},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return TeamMemberResponse(
        user_id=membership.user_id,
        name=membership.user.name,
        email=membership.user.email,
        role=membership.role,
        joined_at=membership.created_at,
    )


@router.delete("/members/{member_user_id}")
async def remove_team_member(
    member_user_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_owner),
    db: AsyncSession = Depends(get_tenant_db),
) -> Dict[str, Any]:
    """Remove a team member from the business tenant."""
    user, business, _, _ = auth_ctx

    stmt = (
        select(Membership)
        .options(selectinload(Membership.user))
        .where(
            Membership.user_id == member_user_id,
            Membership.business_id == business.id,
        )
    )
    membership = (await db.execute(stmt)).scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Member '{member_user_id}' not found in this business.",
        )

    # Prevent removing the last owner
    if membership.role == Role.OWNER.value:
        owner_count_stmt = select(func.count(Membership.id)).where(
            Membership.business_id == business.id,
            Membership.role == Role.OWNER.value,
        )
        owner_count = (await db.execute(owner_count_stmt)).scalar() or 0
        if owner_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove the only owner. Please assign another owner first.",
            )

    email = membership.user.email
    await db.delete(membership)

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="remove_team_member",
        resource_type="membership",
        resource_id=str(membership.id),
        changes={"removed_user_id": str(member_user_id), "email": email, "role": membership.role},
        ip_address=request.client.host if request.client else None,
    )
    await db.flush()

    return {"status": "ok", "message": f"Member '{email}' has been removed from {business.name}."}
