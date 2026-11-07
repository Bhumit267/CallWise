"""Analytics API router: calls per day, conversion, top services, missed questions, latency, and busiest hours."""

from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional
import uuid
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from callwise.api.deps import get_tenant_db
from callwise.api.permissions import require_staff
from callwise.api.schemas import parse_query_datetime
from callwise.db.models import (
    Appointment,
    Business,
    Call,
    CallTurn,
    KnowledgeMiss,
    Message,
    Service,
    Session as UserSession,
    Transfer,
    User,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class DailyCalls(BaseModel):
    date: str
    total: int
    answered: int
    transferred: int
    message_taken: int


class TopServiceItem(BaseModel):
    service_id: uuid.UUID
    name: str
    booking_count: int
    revenue: float


class TopMissedQuestionItem(BaseModel):
    query: str
    count: int
    status: str


class LatencyMetrics(BaseModel):
    median_ms: float
    p95_ms: float
    sample_count: int


class HourDistribution(BaseModel):
    hour: int
    call_count: int


class AnalyticsOverviewResponse(BaseModel):
    date_range_start: str
    date_range_end: str
    timezone: str
    total_calls: int
    answered_count: int
    transferred_count: int
    message_taken_count: int
    booking_conversion_rate: float
    calls_per_day: List[DailyCalls]
    top_services: List[TopServiceItem]
    top_missed_questions: List[TopMissedQuestionItem]
    latency_metrics: LatencyMetrics
    busiest_hours: List[HourDistribution]


@router.get("", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    start_date: Optional[str] = Query(None, description="Start date (ISO-8601)"),
    end_date: Optional[str] = Query(None, description="End date (ISO-8601)"),
    auth_ctx: tuple[User, Business, str, UserSession] = Depends(require_staff),
    db: AsyncSession = Depends(get_tenant_db),
) -> AnalyticsOverviewResponse:
    """Retrieve operational and business performance analytics respecting tenant timezone."""
    _, business, _, _ = auth_ctx

    try:
        biz_tz = ZoneInfo(business.timezone)
    except Exception:
        biz_tz = ZoneInfo("UTC")

    now_utc = datetime.now(timezone.utc)
    start_dt = parse_query_datetime(start_date) or (now_utc - timedelta(days=30))
    end_dt = parse_query_datetime(end_date) or now_utc

    # 1. Fetch Calls in date range with relationships eager loaded to prevent N+1 queries
    call_stmt = (
        select(Call)
        .options(
            selectinload(Call.appointments),
            selectinload(Call.messages),
            selectinload(Call.transfers),
        )
        .where(
            Call.business_id == business.id,
            Call.started_at >= start_dt,
            Call.started_at <= end_dt,
        )
    )
    calls = (await db.execute(call_stmt)).scalars().all()

    total_calls = len(calls)
    transferred_count = 0
    message_taken_count = 0
    answered_count = 0

    daily_map: Dict[str, Dict[str, int]] = {}
    hour_counts: Dict[int, int] = {h: 0 for h in range(24)}

    for c in calls:
        # Business local date & hour
        local_time = c.started_at.astimezone(biz_tz)
        date_str = local_time.strftime("%Y-%m-%d")
        hour_counts[local_time.hour] += 1

        if date_str not in daily_map:
            daily_map[date_str] = {"total": 0, "answered": 0, "transferred": 0, "message_taken": 0}

        daily_map[date_str]["total"] += 1

        if len(c.transfers) > 0:
            transferred_count += 1
            daily_map[date_str]["transferred"] += 1
        elif len(c.messages) > 0:
            message_taken_count += 1
            daily_map[date_str]["message_taken"] += 1
        else:
            answered_count += 1
            daily_map[date_str]["answered"] += 1

    daily_list = [
        DailyCalls(
            date=d,
            total=stats["total"],
            answered=stats["answered"],
            transferred=stats["transferred"],
            message_taken=stats["message_taken"],
        )
        for d, stats in sorted(daily_map.items())
    ]

    # 2. Appointments & Conversion
    app_stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(
            Appointment.business_id == business.id,
            Appointment.status == "booked",
            or_(
                Appointment.created_at.between(start_dt, end_dt),
                Appointment.start_at.between(start_dt, end_dt),
            ),
        )
    )
    appointments = (await db.execute(app_stmt)).scalars().all()
    booked_count = len(appointments)
    conversion_rate = round(booked_count / total_calls, 4) if total_calls > 0 else 0.0

    # Service breakdown
    service_stats: Dict[uuid.UUID, Dict[str, Any]] = {}
    for a in appointments:
        if not a.service:
            continue
        sid = a.service.id
        if sid not in service_stats:
            service_stats[sid] = {"name": a.service.name, "count": 0, "revenue": 0.0}
        service_stats[sid]["count"] += 1
        service_stats[sid]["revenue"] += a.service.price

    top_services = [
        TopServiceItem(
            service_id=sid,
            name=data["name"],
            booking_count=data["count"],
            revenue=data["revenue"],
        )
        for sid, data in sorted(service_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    ]

    # 3. Top Missed Questions
    miss_stmt = (
        select(
            func.min(KnowledgeMiss.query).label("query"),
            func.count(KnowledgeMiss.id).label("count"),
            KnowledgeMiss.status.label("status"),
        )
        .where(
            KnowledgeMiss.business_id == business.id,
            KnowledgeMiss.created_at >= start_dt,
            KnowledgeMiss.created_at <= end_dt,
        )
        .group_by(func.lower(KnowledgeMiss.query), KnowledgeMiss.status)
        .order_by(func.count(KnowledgeMiss.id).desc())
        .limit(10)
    )
    miss_rows = (await db.execute(miss_stmt)).all()
    top_misses = [
        TopMissedQuestionItem(query=row.query, count=row.count, status=row.status)
        for row in miss_rows
    ]

    # 4. Latency Metrics (Median and P95)
    turn_stmt = (
        select(CallTurn.latency_ms)
        .join(Call, CallTurn.call_id == Call.id)
        .where(
            CallTurn.business_id == business.id,
            CallTurn.speaker == "agent",
            CallTurn.latency_ms.isnot(None),
            Call.started_at >= start_dt,
            Call.started_at <= end_dt,
        )
    )
    latencies = [val for val in (await db.execute(turn_stmt)).scalars().all() if val is not None]
    latencies.sort()

    median_ms = 0.0
    p95_ms = 0.0
    sample_count = len(latencies)
    if sample_count > 0:
        mid = sample_count // 2
        median_ms = latencies[mid] if sample_count % 2 != 0 else (latencies[mid - 1] + latencies[mid]) / 2.0
        p95_idx = min(int(math.ceil(0.95 * sample_count)) - 1, sample_count - 1)
        p95_ms = latencies[p95_idx]

    busiest_hours = [HourDistribution(hour=h, call_count=cnt) for h, cnt in sorted(hour_counts.items())]

    return AnalyticsOverviewResponse(
        date_range_start=start_dt.isoformat(),
        date_range_end=end_dt.isoformat(),
        timezone=business.timezone,
        total_calls=total_calls,
        answered_count=answered_count,
        transferred_count=transferred_count,
        message_taken_count=message_taken_count,
        booking_conversion_rate=conversion_rate,
        calls_per_day=daily_list,
        top_services=top_services,
        top_missed_questions=top_misses,
        latency_metrics=LatencyMetrics(
            median_ms=round(median_ms, 2),
            p95_ms=round(p95_ms, 2),
            sample_count=sample_count,
        ),
        busiest_hours=busiest_hours,
    )
