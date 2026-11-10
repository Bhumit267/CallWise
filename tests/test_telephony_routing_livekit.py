"""Tests for telephony routing, LiveKit SIP provider, and caller ID contact matching."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.db.models import BlocklistEntry, Business, Contact, PhoneNumber
from callwise.db.session import get_async_session
from callwise.providers.telephony import (
    LiveKitSIPTelephonyProvider,
    MockTelephonyProvider,
    get_telephony_provider,
)
from callwise.telephony.router import (
    create_inbound_call_record_async,
    normalize_e164,
    resolve_inbound_call_async,
)


def test_normalize_e164():
    """Verify phone normalization handles various formats."""
    assert normalize_e164("+1 (555) 234-5678") == "+15552345678"
    assert normalize_e164("5552345678") == "+15552345678"
    assert normalize_e164("+44 20 7946 0958") == "+442079460958"


@pytest.mark.asyncio
async def test_resolve_inbound_call_success_and_contact_match():
    """Verify dialed number resolves to business and creates/matches contact."""
    biz_id = uuid.uuid4()
    e164_dialed = f"+1555{uuid.uuid4().int % 10000000:07d}"
    caller_phone = "+15558889999"

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Downtown Dental",
            business_type="Dental",
            greeting="Hello Downtown Dental",
            hours={},
        )
        session.add(biz)

        phone = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_id,
            e164_number=e164_dialed,
            provider="livekit",
            label="Inbound Front Desk",
            is_active=True,
        )
        session.add(phone)
        await session.commit()

    # Route inbound call
    result = await resolve_inbound_call_async(
        dialed_number=e164_dialed,
        caller_number=caller_phone,
        caller_name="Sarah Connor",
    )

    assert result.matched is True
    assert result.business.id == biz_id
    assert result.contact is not None
    assert result.contact.phone == caller_phone
    assert result.contact.name == "Sarah Connor"
    assert result.is_blocked is False

    # Create Call session record
    call = await create_inbound_call_record_async(result, caller_number=caller_phone)
    assert call.business_id == biz_id
    assert call.contact_id == result.contact.id
    assert call.caller_number == caller_phone


@pytest.mark.asyncio
async def test_resolve_inbound_call_unknown_number():
    """Verify unknown dialed number yields polite rejection message."""
    result = await resolve_inbound_call_async(
        dialed_number="+15550009999",
        caller_number="+15551234567",
    )

    assert result.matched is False
    assert result.reject_reason == "unknown_dialed_number"
    assert "not currently in service" in result.reply_message


@pytest.mark.asyncio
async def test_resolve_inbound_call_blocklist_enforcement():
    """Verify blocklisted caller number is rejected before agent interaction."""
    biz_id = uuid.uuid4()
    e164_dialed = f"+1555{uuid.uuid4().int % 10000000:07d}"
    blocked_caller = "+15559990001"

    async with get_async_session() as session:
        biz = Business(
            id=biz_id,
            name="Secure Clinic",
            business_type="Medical",
            greeting="Hello",
            hours={},
        )
        session.add(biz)

        phone = PhoneNumber(
            id=uuid.uuid4(),
            business_id=biz_id,
            e164_number=e164_dialed,
            is_active=True,
        )
        session.add(phone)

        block = BlocklistEntry(
            id=uuid.uuid4(),
            business_id=biz_id,
            identifier_type="phone",
            identifier_value=blocked_caller,
            reason="Abusive spammer",
        )
        session.add(block)
        await session.commit()

    result = await resolve_inbound_call_async(
        dialed_number=e164_dialed,
        caller_number=blocked_caller,
    )

    assert result.matched is True
    assert result.is_blocked is True
    assert result.reject_reason == "caller_in_blocklist"
    assert "unable to connect your call" in result.reply_message


@pytest.mark.asyncio
async def test_livekit_sip_telephony_provider_mocked():
    """Verify LiveKit SIP provider dry-run and API interaction."""
    provider = LiveKitSIPTelephonyProvider(sip_trunk_uri="sip:trunk.livekit.cloud")
    res = await provider.transfer_call(
        call_id=uuid.uuid4(),
        target_number="+15551234567",
        reason="Test SIP escalation",
    )
    assert res.success is True
    assert res.status == "completed"
    assert "+15551234567" in res.message


def test_get_telephony_provider_factory():
    """Verify factory returns appropriate provider implementation."""
    mock_p = get_telephony_provider("mock")
    assert isinstance(mock_p, MockTelephonyProvider)

    sip_p = get_telephony_provider("sip")
    assert isinstance(sip_p, LiveKitSIPTelephonyProvider)

    livekit_p = get_telephony_provider("livekit")
    assert isinstance(livekit_p, LiveKitSIPTelephonyProvider)
