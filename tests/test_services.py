"""Unit and integration tests for Step 1: Services, appointments schema, and CLI commands."""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from callwise.cli import app
from callwise.db.models import (
    Appointment,
    Business,
    Call,
    Notification,
    Reminder,
    Service,
    Transfer,
    VerificationAttempt,
)
from callwise.db.seed import DENTAL_CLINIC_ID, SALON_SPA_ID, run_seed
from callwise.db.session import get_sync_session

runner = CliRunner()


def test_seed_creates_services_and_contact_info():
    """Verify seed script populates demo services, transfer_number, and notification_email."""
    run_seed()

    with get_sync_session() as session:
        dental = session.get(Business, DENTAL_CLINIC_ID)
        assert dental is not None
        assert dental.transfer_number == "+1-617-555-0100"
        assert dental.notification_email == "frontdesk@brightsmilefamilydental.com"

        dental_services = session.scalars(
            select(Service).where(Service.business_id == DENTAL_CLINIC_ID)
        ).all()
        assert len(dental_services) >= 4
        service_names = [s.name for s in dental_services]
        assert "Routine Cleaning & Exam" in service_names
        assert "Zoom In-Office Teeth Whitening" in service_names

        whitening = next(s for s in dental_services if s.name == "Zoom In-Office Teeth Whitening")
        assert whitening.duration_minutes == 60
        assert whitening.price == 350.0

        salon = session.get(Business, SALON_SPA_ID)
        assert salon is not None
        assert salon.transfer_number == "+1-310-555-0200"
        assert salon.notification_email == "reception@luxeglowsalon.com"

        salon_services = session.scalars(
            select(Service).where(Service.business_id == SALON_SPA_ID)
        ).all()
        assert len(salon_services) >= 4
        salon_names = [s.name for s in salon_services]
        assert "Full Custom Balayage" in salon_names


def test_seed_services_idempotent():
    """Verify running seed multiple times does not duplicate services."""
    run_seed()
    run_seed()

    with get_sync_session() as session:
        dental_services = session.scalars(
            select(Service).where(Service.business_id == DENTAL_CLINIC_ID)
        ).all()
        names = [s.name for s in dental_services]
        assert len(names) == len(set(names))


def test_phase2_database_models_persistence():
    """Verify all 6 new models persist and link to business/call properly."""
    biz_id = uuid.uuid4()
    call_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with get_sync_session() as session:
        biz = Business(
            id=biz_id,
            name="Orion Wellness Clinic",
            business_type="Wellness Center",
            greeting="Welcome to Orion Wellness.",
            tone="calm and attentive",
            timezone="America/Denver",
            hours={},
            transfer_number="+1-303-555-9999",
            notification_email="alerts@orionwellness.com",
        )
        session.add(biz)

        call = Call(
            id=call_id,
            business_id=biz_id,
            caller_number="+1-303-555-1234",
        )
        session.add(call)

        svc = Service(
            business_id=biz_id,
            name="Acupuncture Therapy",
            duration_minutes=45,
            price=95.0,
            description="Traditional acupuncture session",
            is_active=True,
        )
        session.add(svc)
        session.flush()

        apt = Appointment(
            business_id=biz_id,
            service_id=svc.id,
            call_id=call_id,
            customer_name="Dana Scully",
            customer_phone="+1-303-555-1234",
            customer_email="dana@example.com",
            start_at=now + timedelta(days=1),
            end_at=now + timedelta(days=1, minutes=45),
            status="booked",
            booking_code_hash="hashed_code_123",
            external_event_id="cal_event_789",
        )
        session.add(apt)
        session.flush()

        attempt = VerificationAttempt(
            business_id=biz_id,
            appointment_id=apt.id,
            call_id=call_id,
            phone="+1-303-555-1234",
            success=True,
        )
        session.add(attempt)

        transfer = Transfer(
            business_id=biz_id,
            call_id=call_id,
            reason="Caller requested human supervisor",
            status="initiated",
        )
        session.add(transfer)

        notif = Notification(
            business_id=biz_id,
            type="booking_confirmation",
            recipient="dana@example.com",
            status="pending",
        )
        session.add(notif)

        reminder = Reminder(
            business_id=biz_id,
            appointment_id=apt.id,
            send_at=now + timedelta(hours=12),
            status="pending",
        )
        session.add(reminder)
        session.commit()

    # Verify retrieval
    with get_sync_session() as session:
        saved_apt = session.get(Appointment, apt.id)
        assert saved_apt is not None
        assert saved_apt.customer_name == "Dana Scully"
        assert saved_apt.service.name == "Acupuncture Therapy"
        assert saved_apt.call.caller_number == "+1-303-555-1234"
        assert len(saved_apt.verification_attempts) == 1
        assert len(saved_apt.reminders) == 1

        saved_biz = session.get(Business, biz_id)
        assert len(saved_biz.services) == 1
        assert len(saved_biz.transfers) == 1
        assert len(saved_biz.notifications) == 1


def test_cli_list_and_add_service():
    """Verify CLI commands list-services and add-service."""
    run_seed()

    # Test list-services
    res1 = runner.invoke(app, ["list-services", "--business-id", str(DENTAL_CLINIC_ID)])
    assert res1.exit_code == 0
    assert "Routine Cleaning & Exam" in res1.output
    assert "Zoom In-Office Teeth Whitening" in res1.output
    assert "$350.00" in res1.output

    # Test add-service
    res2 = runner.invoke(
        app,
        [
            "add-service",
            "--business-id",
            str(DENTAL_CLINIC_ID),
            "--name",
            "Fluoride Treatment",
            "--duration",
            "15",
            "--price",
            "45.00",
            "--description",
            "Enamel-strengthening topical fluoride treatment",
        ],
    )
    assert res2.exit_code == 0
    assert "Fluoride Treatment" in res2.output
    assert "$45.00" in res2.output

    # Verify newly added service appears in list-services
    res3 = runner.invoke(app, ["list-services", "--business-id", str(DENTAL_CLINIC_ID)])
    assert res3.exit_code == 0
    assert "Fluoride Treatment" in res3.output
    assert "$45.00" in res3.output


def test_cli_add_service_validation():
    """Verify input validation errors on add-service command."""
    # Invalid business ID
    res1 = runner.invoke(
        app,
        ["add-service", "--business-id", "invalid-uuid", "--name", "Test", "--duration", "30", "--price", "50"],
    )
    assert res1.exit_code != 0
    assert "Invalid business UUID" in res1.output

    # Negative duration
    res2 = runner.invoke(
        app,
        ["add-service", "--business-id", str(DENTAL_CLINIC_ID), "--name", "Test", "--duration", "-10", "--price", "50"],
    )
    assert res2.exit_code != 0
    assert "positive integer" in res2.output

    # Negative price
    res3 = runner.invoke(
        app,
        ["add-service", "--business-id", str(DENTAL_CLINIC_ID), "--name", "Test", "--duration", "30", "--price", "-5"],
    )
    assert res3.exit_code != 0
    assert "non-negative" in res3.output

