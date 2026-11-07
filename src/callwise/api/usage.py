"""FastAPI router for tenant usage metrics, cost tracking, and limit dashboards."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import Date, cast, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_manager, require_owner, require_staff
from callwise.calls.usage import (
    PRICING_TABLE,
    get_or_create_usage_limits,
)
from callwise.db.models import Business, Session as UserSession, UsageLimits, UsageRecord, User

router = APIRouter(prefix="/usage", tags=["Usage & Limits"])


class UsageLimitsResponse(BaseModel):
    voice_minutes_per_month: int
    chat_messages_per_month: int
    max_concurrent_calls: int
    max_call_duration_seconds: int
    llm_tokens_per_month: int
    hard_limit_enforced: bool


class CurrentMonthUsage(BaseModel):
    voice_minutes: float
    chat_messages: int
    llm_tokens: int
    total_cost_usd: float


class DailyUsageItem(BaseModel):
    date: str
    voice_minutes: float
    chat_messages: int
    total_cost_usd: float


class UsageSummaryResponse(BaseModel):
    limits: UsageLimitsResponse
    current_month: CurrentMonthUsage
    daily_usage: List[DailyUsageItem]
    pricing_table: Dict[str, Any]


class UsageRecordItem(BaseModel):
    id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    session_type: str
    duration_seconds: int
    stt_seconds: float
    tts_characters: int
    llm_input_tokens: int
    llm_output_tokens: int
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    estimated_cost_usd: float
    created_at: datetime


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> UsageSummaryResponse:
    """Retrieve usage metrics, limits, and daily cost estimation for the active tenant."""
    _, business, _, _ = auth_ctx

    # 1. Fetch Limits
    limits = await get_or_create_usage_limits(db, business.id)

    # 2. Month-to-date metrics
    now = datetime.now(timezone.utc)
    start_of_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)

    # Aggregates for voice vs chat
    voice_stmt = select(
        func.coalesce(func.sum(UsageRecord.duration_seconds), 0),
        func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0.0),
    ).where(
        UsageRecord.business_id == business.id,
        UsageRecord.created_at >= start_of_month,
        UsageRecord.session_type == "phone",
    )
    voice_row = (await db.execute(voice_stmt)).one()
    voice_duration_secs = voice_row[0]
    voice_cost = float(voice_row[1])

    chat_stmt = select(
        func.coalesce(func.count(UsageRecord.id), 0),
        func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0.0),
    ).where(
        UsageRecord.business_id == business.id,
        UsageRecord.created_at >= start_of_month,
        UsageRecord.session_type.in_(["widget", "chat"]),
    )
    chat_row = (await db.execute(chat_stmt)).one()
    chat_sessions = chat_row[0]
    chat_cost = float(chat_row[1])

    # Total tokens
    tokens_stmt = select(
        func.coalesce(
            func.sum(UsageRecord.llm_input_tokens + UsageRecord.llm_output_tokens), 0
        ),
        func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0.0),
    ).where(
        UsageRecord.business_id == business.id,
        UsageRecord.created_at >= start_of_month,
    )
    tokens_row = (await db.execute(tokens_stmt)).one()
    total_tokens = tokens_row[0]
    total_cost_usd = float(tokens_row[1])

    current_month = CurrentMonthUsage(
        voice_minutes=round(voice_duration_secs / 60.0, 1),
        chat_messages=chat_sessions,
        llm_tokens=total_tokens,
        total_cost_usd=round(total_cost_usd, 4),
    )

    # 3. 30-day daily breakdown
    daily_items: List[DailyUsageItem] = []
    thirty_days_ago = now - timedelta(days=30)

    # Query usage records grouped by date
    day_col = cast(UsageRecord.created_at, Date)
    daily_stmt = (
        select(
            day_col.label("day"),
            func.coalesce(func.sum(UsageRecord.duration_seconds), 0).label("secs"),
            func.coalesce(func.count(UsageRecord.id), 0).label("count"),
            func.coalesce(func.sum(UsageRecord.estimated_cost_usd), 0.0).label("cost"),
        )
        .where(
            UsageRecord.business_id == business.id,
            UsageRecord.created_at >= thirty_days_ago,
        )
        .group_by(day_col)
        .order_by(day_col.asc())
    )
    daily_results = (await db.execute(daily_stmt)).all()

    daily_map = {
        row.day.strftime("%Y-%m-%d") if hasattr(row.day, "strftime") else str(row.day)[:10]: row
        for row in daily_results
    }

    # Generate daily items for each of the last 14 days
    for day_offset in range(13, -1, -1):
        target_day = (now - timedelta(days=day_offset)).strftime("%Y-%m-%d")
        if target_day in daily_map:
            r = daily_map[target_day]
            daily_items.append(
                DailyUsageItem(
                    date=target_day,
                    voice_minutes=round(r.secs / 60.0, 1),
                    chat_messages=r.count,
                    total_cost_usd=round(float(r.cost), 4),
                )
            )
        else:
            daily_items.append(
                DailyUsageItem(
                    date=target_day,
                    voice_minutes=0.0,
                    chat_messages=0,
                    total_cost_usd=0.0,
                )
            )

    return UsageSummaryResponse(
        limits=UsageLimitsResponse(
            voice_minutes_per_month=limits.voice_minutes_per_month,
            chat_messages_per_month=limits.chat_messages_per_month,
            max_concurrent_calls=limits.max_concurrent_calls,
            max_call_duration_seconds=limits.max_call_duration_seconds,
            llm_tokens_per_month=limits.llm_tokens_per_month,
            hard_limit_enforced=limits.hard_limit_enforced,
        ),
        current_month=current_month,
        daily_usage=daily_items,
        pricing_table=PRICING_TABLE,
    )


@router.get("/calls", response_model=List[UsageRecordItem])
async def list_recent_call_usage(
    limit: int = Query(25, ge=1, le=100),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> List[UsageRecordItem]:
    """List recent call and chat usage records with per-session cost breakdown."""
    _, business, _, _ = auth_ctx

    stmt = (
        select(UsageRecord)
        .where(UsageRecord.business_id == business.id)
        .order_by(desc(UsageRecord.created_at))
        .limit(limit)
    )
    records = (await db.execute(stmt)).scalars().all()
    return records
