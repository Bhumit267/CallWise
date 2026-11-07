"""FastAPI API routes for managing Phone Numbers."""

from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.api.audit import record_audit_log
from callwise.api.deps import get_auth_context, get_db, get_tenant_db
from callwise.api.permissions import require_manager, require_owner, require_staff
from callwise.db.models import Business, PhoneNumber, Session as UserSession, User
from callwise.telephony.router import normalize_e164

router = APIRouter(prefix="/phone-numbers", tags=["Phone Numbers"])


class PhoneNumberCreate(BaseModel):
    e164_number: str = Field(..., min_length=7, max_length=50)
    provider: str = Field(default="livekit", max_length=50)
    label: str = Field(default="Main Inbound", max_length=100)
    is_active: bool = True


class PhoneNumberUpdate(BaseModel):
    label: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class PhoneNumberResponse(BaseModel):
    id: uuid.UUID
    business_id: uuid.UUID
    e164_number: str
    provider: str
    label: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[PhoneNumberResponse]:
    """List all phone numbers configured for the active business tenant."""
    _, business, _, _ = auth_ctx
    stmt = (
        select(PhoneNumber)
        .where(PhoneNumber.business_id == business.id)
        .order_by(PhoneNumber.created_at.asc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    payload: PhoneNumberCreate,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> PhoneNumberResponse:
    """Assign an inbound phone number to the current business tenant."""
    user, business, _, _ = auth_ctx
    norm_phone = normalize_e164(payload.e164_number)

    # Check for uniqueness across the platform
    existing_stmt = select(PhoneNumber).where(PhoneNumber.e164_number == norm_phone)
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phone number {norm_phone} is already assigned to a business tenant.",
        )

    phone = PhoneNumber(
        id=uuid.uuid4(),
        business_id=business.id,
        e164_number=norm_phone,
        provider=payload.provider.lower().strip(),
        label=payload.label.strip(),
        is_active=payload.is_active,
    )
    db.add(phone)
    await db.flush()

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="phone_number_create",
        resource_type="phone_number",
        resource_id=str(phone.id),
        changes={"e164_number": phone.e164_number, "label": phone.label},
        ip_address=request.client.host if request.client else None,
    )
    await db.commit()
    return phone


@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    phone_id: uuid.UUID,
    request: Request,
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Remove a phone number mapping from the current business tenant."""
    user, business, _, _ = auth_ctx
    stmt = select(PhoneNumber).where(PhoneNumber.id == phone_id, PhoneNumber.business_id == business.id)
    phone = (await db.execute(stmt)).scalar_one_or_none()
    if not phone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Phone number not found.")

    await record_audit_log(
        db=db,
        business_id=business.id,
        user_id=user.id,
        action="phone_number_delete",
        resource_type="phone_number",
        resource_id=str(phone.id),
        changes={"e164_number": phone.e164_number},
        ip_address=request.client.host if request.client else None,
    )
    await db.delete(phone)
    await db.commit()
