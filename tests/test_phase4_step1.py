"""Tests for Step 1: Phase 4 database models, relationships, and PostgreSQL RLS policies."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from callwise.db.models import (
    Business,
    BlocklistEntry,
    PhoneNumber,
    UsageLimits,
    UsageRecord,
    WidgetSettings,
)
from callwise.db.session import get_async_session


@pytest.mark.asyncio
async def test_phase4_models_crud_and_relationships():
    """Verify PhoneNumber, UsageLimits, WidgetSettings, UsageRecord, and Blocklist CRUD."""
    async with get_async_session() as session:
        # 1. Create Business
        biz = Business(
            id=uuid.uuid4(),
            name="Phase 4 Test Medical Practice",
            business_type="Healthcare",
            greeting="Welcome to Phase 4 test clinic.",
            tone="professional",
            timezone="America/New_York",
            hours={"monday": {"open": "09:00", "close": "17:00", "closed": False}},
        )
        session.add(biz)
        await session.flush()

        # 2. Add PhoneNumber
        phone = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz.id,
            e164_number=f"+1555{uuid.uuid4().hex[:7]}",
            provider="livekit",
            label="Toll Free Clinic Line",
            is_active=True,
        )
        session.add(phone)

        # 3. Add UsageLimits
        limits = UsageLimits(
            id=uuid.uuid4(),
            business_id=biz.id,
            voice_minutes_per_month=500,
            chat_messages_per_month=2000,
            max_concurrent_calls=5,
            max_call_duration_seconds=900,
            llm_tokens_per_month=1000000,
            hard_limit_enforced=True,
        )
        session.add(limits)

        # 4. Add WidgetSettings
        widget = WidgetSettings(
            id=uuid.uuid4(),
            business_id=biz.id,
            public_key=f"cw_live_{uuid.uuid4().hex}",
            is_enabled=True,
            allowed_origins="https://clinic.example.com",
            primary_color="#10B981",
            greeting_message="Hello from our medical chat receptionist!",
            ask_lead_capture=True,
            require_lead_name=True,
            allow_booking=True,
        )
        session.add(widget)

        # 5. Add UsageRecord
        usage = UsageRecord(
            id=uuid.uuid4(),
            business_id=biz.id,
            session_type="phone",
            duration_seconds=180,
            stt_seconds=175.5,
            tts_characters=450,
            llm_input_tokens=1200,
            llm_output_tokens=300,
            llm_provider="groq",
            llm_model="openai/gpt-oss-120b",
            estimated_cost_usd=0.015,
        )
        session.add(usage)

        # 6. Add BlocklistEntry
        blocked = BlocklistEntry(
            id=uuid.uuid4(),
            business_id=biz.id,
            identifier_type="phone",
            identifier_value="+15559990000",
            reason="Repeated spam robo-caller",
        )
        session.add(blocked)
        await session.commit()

    # 7. Query back through Business relationships with eager loading
    async with get_async_session() as session:
        query = (
            select(Business)
            .where(Business.id == biz.id)
            .options(
                selectinload(Business.phone_numbers),
                selectinload(Business.usage_limits),
                selectinload(Business.widget_settings),
                selectinload(Business.usage_records),
                selectinload(Business.blocklist_entries),
            )
        )
        loaded_biz = (await session.execute(query)).scalar_one()

        assert loaded_biz.name == "Phase 4 Test Medical Practice"
        assert len(loaded_biz.phone_numbers) == 1
        assert loaded_biz.phone_numbers[0].label == "Toll Free Clinic Line"
        assert loaded_biz.usage_limits is not None
        assert loaded_biz.usage_limits.voice_minutes_per_month == 500
        assert loaded_biz.widget_settings is not None
        assert loaded_biz.widget_settings.primary_color == "#10B981"
        assert len(loaded_biz.usage_records) == 1
        assert loaded_biz.usage_records[0].duration_seconds == 180
        assert len(loaded_biz.blocklist_entries) == 1
        assert loaded_biz.blocklist_entries[0].identifier_value == "+15559990000"


@pytest.mark.asyncio
async def test_phase4_rls_tenant_isolation():
    """Verify PostgreSQL Row-Level Security blocks cross-tenant reads on Phase 4 tables."""
    biz_a_id = uuid.uuid4()
    biz_b_id = uuid.uuid4()

    async with get_async_session() as session:
        # Seed both businesses and phone numbers
        biz_a = Business(
            id=biz_a_id,
            name="Tenant A Line",
            business_type="Medical",
            greeting="Hello A",
            hours={},
        )
        biz_b = Business(
            id=biz_b_id,
            name="Tenant B Line",
            business_type="Legal",
            greeting="Hello B",
            hours={},
        )
        session.add_all([biz_a, biz_b])

        phone_a = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_a_id,
            e164_number=f"+1555{uuid.uuid4().hex[:7]}",
            provider="livekit",
            label="Tenant A Support",
        )
        phone_b = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_b_id,
            e164_number=f"+1555{uuid.uuid4().hex[:7]}",
            provider="livekit",
            label="Tenant B Support",
        )
        session.add_all([phone_a, phone_b])
        await session.commit()

    # Query scoped to Tenant A under callwise_app role
    async with get_async_session() as session:
        await session.execute(text("SET LOCAL ROLE callwise_app;"))
        await session.execute(text(f"SET LOCAL app.current_business_id = '{biz_a_id}';"))
        res_a = await session.execute(select(PhoneNumber))
        phones_a = res_a.scalars().all()
        phone_biz_ids = {p.business_id for p in phones_a}
        assert biz_a_id in phone_biz_ids
        assert biz_b_id not in phone_biz_ids

    # Query scoped to Tenant B under callwise_app role
    async with get_async_session() as session:
        await session.execute(text("SET LOCAL ROLE callwise_app;"))
        await session.execute(text(f"SET LOCAL app.current_business_id = '{biz_b_id}';"))
        res_b = await session.execute(select(PhoneNumber))
        phones_b = res_b.scalars().all()
        phone_biz_ids = {p.business_id for p in phones_b}
        assert biz_b_id in phone_biz_ids
        assert biz_a_id not in phone_biz_ids
