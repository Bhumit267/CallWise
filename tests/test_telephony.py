"""Tests for TelephonyProvider implementations, LiveKit SIP scaffold, and live transfer execution."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select

from callwise.booking.transfer import execute_transfer
from callwise.db.models import Business, Call, Notification, Transfer
from callwise.db.session import AsyncSessionLocal
from callwise.providers.email import ConsoleEmailProvider
from callwise.providers.telephony import (
    MockTelephonyProvider,
    SIPTelephonyProvider,
    TelephonyProvider,
    TransferResult,
    get_telephony_provider,
)


@pytest.mark.asyncio
async def test_mock_telephony_provider_success():
    """Verify MockTelephonyProvider records transfer and returns success."""
    provider = MockTelephonyProvider()
    call_id = uuid.uuid4()
    target_num = "+15551234567"
    reason = "Caller requests speaking to clinic manager"

    res = await provider.transfer_call(call_id=call_id, target_number=target_num, reason=reason)
    assert res.success is True
    assert res.status == "completed"
    assert res.target_phone == target_num
    assert len(provider.recorded_transfers) == 1
    assert provider.recorded_transfers[0]["call_id"] == call_id
    assert provider.recorded_transfers[0]["target_number"] == target_num

    provider.clear()
    assert len(provider.recorded_transfers) == 0


@pytest.mark.asyncio
async def test_mock_telephony_provider_busy():
    """Verify MockTelephonyProvider simulates busy line."""
    provider = MockTelephonyProvider(simulate_busy=True)
    call_id = uuid.uuid4()

    is_avail = await provider.is_available("+15551234567")
    assert is_avail is False

    res = await provider.transfer_call(call_id=call_id, target_number="+15551234567", reason="Urgent issue")
    assert res.success is False
    assert res.status == "failed"
    assert "busy" in res.message.lower()


@pytest.mark.asyncio
async def test_mock_telephony_provider_failure():
    """Verify MockTelephonyProvider handles failure mode."""
    provider = MockTelephonyProvider(should_succeed=False)
    res = await provider.transfer_call(call_id=uuid.uuid4(), target_number="+15551234567", reason="Help")
    assert res.success is False
    assert res.status == "failed"
    assert "telephony error" in res.message.lower()


def test_sip_provider_and_factory():
    """Verify SIP provider scaffold and factory resolution."""
    # SIP provider without URI
    sip_no_uri = SIPTelephonyProvider(sip_trunk_uri=None)
    import asyncio
    res_no_uri = asyncio.run(sip_no_uri.transfer_call(None, "+15551234567", "Testing"))
    assert res_no_uri.success is False
    assert "not configured" in res_no_uri.message

    # SIP provider with URI
    sip_with_uri = SIPTelephonyProvider(sip_trunk_uri="sip:trunk.livekit.cloud")
    res_with_uri = asyncio.run(sip_with_uri.transfer_call(None, "+15551234567", "Testing"))
    assert res_with_uri.success is True
    assert res_with_uri.status == "completed"

    # Factory tests
    mock_p = get_telephony_provider("mock")
    assert isinstance(mock_p, MockTelephonyProvider)

    sip_p = get_telephony_provider("sip")
    assert isinstance(sip_p, SIPTelephonyProvider)

    with pytest.raises(ValueError, match="Unsupported telephony provider"):
        get_telephony_provider("unsupported_telephony_network")


@pytest.mark.asyncio
async def test_execute_transfer_success_open_hours():
    """Verify successful live call transfer during business hours."""
    biz_id = uuid.uuid4()
    call_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()
    mock_telephony = MockTelephonyProvider()

    hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
        "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
        "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
        "thursday": {"open": "09:00", "close": "17:00", "closed": False},
        "friday": {"open": "09:00", "close": "17:00", "closed": False},
        "saturday": {"open": None, "close": None, "closed": True},
        "sunday": {"open": None, "close": None, "closed": True},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Sunny Smiles Dental",
                business_type="Dental Clinic",
                greeting="Welcome to Sunny Smiles",
                tone="Friendly",
                timezone="UTC",
                hours=hours,
                transfer_number="+15559876543",
                notification_email="owner@sunnysmiles.com",
            )
            session.add(biz)

            call = Call(
                id=call_id,
                business_id=biz_id,
                caller_number="+15550001122",
            )
            session.add(call)

    # Reference time: Wednesday 11:00 UTC (during open hours)
    ref_time = datetime(2026, 11, 11, 11, 0, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await execute_transfer(
                session=session,
                business_id=biz_id,
                call_id=call_id,
                reason="Patient has billing discrepancy questions",
                telephony_provider=mock_telephony,
                email_provider=mock_email,
                reference_now=ref_time,
            )

    assert result.success is True
    assert result.status == "completed"
    assert result.target_phone == "+15559876543"
    assert "+15559876543" in result.message

    # Check database transfer record
    async with AsyncSessionLocal() as session:
        stmt = select(Transfer).where(Transfer.business_id == biz_id)
        transfers = (await session.execute(stmt)).scalars().all()
        assert len(transfers) == 1
        assert transfers[0].status == "completed"
        assert transfers[0].call_id == call_id

        # Verify notification email was dispatched to business owner
        n_stmt = select(Notification).where(
            Notification.business_id == biz_id,
            Notification.type == "owner_transfer_alert",
        )
        notifs = (await session.execute(n_stmt)).scalars().all()
        assert len(notifs) == 1
        assert notifs[0].status == "sent"
        assert notifs[0].recipient == "owner@sunnysmiles.com"


@pytest.mark.asyncio
async def test_execute_transfer_closed_hours_fallback():
    """Verify live transfer falls back to message when office is closed."""
    biz_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()
    mock_telephony = MockTelephonyProvider()

    hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
        "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
        "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
        "thursday": {"open": "09:00", "close": "17:00", "closed": False},
        "friday": {"open": "09:00", "close": "17:00", "closed": False},
        "saturday": {"open": None, "close": None, "closed": True},
        "sunday": {"open": None, "close": None, "closed": True},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Night Dental",
                business_type="Dental Clinic",
                greeting="Hello",
                timezone="UTC",
                hours=hours,
                transfer_number="+15559876543",
                notification_email="owner@nightdental.com",
            )
            session.add(biz)

    # Reference time: Sunday 14:00 UTC (closed day)
    ref_time = datetime(2026, 11, 15, 14, 0, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await execute_transfer(
                session=session,
                business_id=biz_id,
                reason="Caller wants urgent appointment",
                telephony_provider=mock_telephony,
                email_provider=mock_email,
                reference_now=ref_time,
            )

    assert result.success is False
    assert result.status == "fallback_message"
    assert "currently closed" in result.message
    assert "leave a message" in result.message
    # No transfer should have reached the telephony provider
    assert len(mock_telephony.recorded_transfers) == 0

    # Check database transfer record
    async with AsyncSessionLocal() as session:
        stmt = select(Transfer).where(Transfer.business_id == biz_id)
        transfers = (await session.execute(stmt)).scalars().all()
        assert len(transfers) == 1
        assert transfers[0].status == "fallback_message"


@pytest.mark.asyncio
async def test_execute_transfer_missing_transfer_number():
    """Verify live transfer falls back when business has no transfer number set."""
    biz_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()
    mock_telephony = MockTelephonyProvider()

    hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Digital Only Office",
                business_type="Tech Support",
                greeting="Hello",
                timezone="UTC",
                hours=hours,
                transfer_number=None,  # No transfer number
                notification_email="admin@digitaloffice.com",
            )
            session.add(biz)

    ref_time = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)  # Monday 10:00 UTC

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await execute_transfer(
                session=session,
                business_id=biz_id,
                reason="Need human assistance",
                telephony_provider=mock_telephony,
                email_provider=mock_email,
                reference_now=ref_time,
            )

    assert result.success is False
    assert result.status == "fallback_message"
    assert "not currently configured" in result.message


@pytest.mark.asyncio
async def test_execute_transfer_provider_busy():
    """Verify live transfer failure when line is busy."""
    biz_id = uuid.uuid4()
    mock_email = ConsoleEmailProvider()
    mock_telephony = MockTelephonyProvider(simulate_busy=True)

    hours = {
        "monday": {"open": "09:00", "close": "17:00", "closed": False},
    }

    async with AsyncSessionLocal() as session:
        async with session.begin():
            biz = Business(
                id=biz_id,
                name="Busy Office",
                business_type="Legal",
                greeting="Hello",
                timezone="UTC",
                hours=hours,
                transfer_number="+15553334444",
                notification_email="law@busyoffice.com",
            )
            session.add(biz)

    ref_time = datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await execute_transfer(
                session=session,
                business_id=biz_id,
                reason="Legal consultation",
                telephony_provider=mock_telephony,
                email_provider=mock_email,
                reference_now=ref_time,
            )

    assert result.success is False
    assert result.status == "failed"
    assert "line is currently busy" in result.message

    async with AsyncSessionLocal() as session:
        stmt = select(Transfer).where(Transfer.business_id == biz_id)
        transfers = (await session.execute(stmt)).scalars().all()
        assert len(transfers) == 1
        assert transfers[0].status == "failed"
