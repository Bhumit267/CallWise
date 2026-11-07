"""Unit and tenant isolation tests for Step 5 write APIs & background job worker."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_password, hash_token
from callwise.db.models import (
    Appointment,
    AuditLog,
    Business,
    Call,
    Contact,
    Document,
    FollowUp,
    Job,
    KnowledgeMiss,
    Membership,
    Message,
    Service,
    Session as UserSession,
    User,
)
from callwise.db.session import async_engine, get_async_session
from callwise.jobs.worker import process_next_job


@pytest_asyncio.fixture(autouse=True)
async def cleanup():
    """Reset rate limiter and engine pool."""
    auth_rate_limiter.clear_all()
    yield
    auth_rate_limiter.clear_all()
    await async_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def create_tenant(session, biz_name: str, email: str, role: str = "manager"):
    """Helper to provision business, user, membership, and session."""
    now = datetime.now(timezone.utc)
    biz = Business(
        id=uuid.uuid4(),
        name=biz_name,
        business_type="Dental",
        timezone="America/New_York",
        greeting=f"Welcome to {biz_name}",
        tone="professional",
        hours={
            "monday": {"open": "09:00", "close": "17:00", "closed": False},
            "tuesday": {"open": "09:00", "close": "17:00", "closed": False},
            "wednesday": {"open": "09:00", "close": "17:00", "closed": False},
            "thursday": {"open": "09:00", "close": "17:00", "closed": False},
            "friday": {"open": "09:00", "close": "17:00", "closed": False},
            "saturday": {"closed": True},
            "sunday": {"closed": True},
        },
    )
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("SecurePassword123!"),
        name=f"User {biz_name}",
        is_active=True,
    )
    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        business_id=biz.id,
        role=role,
    )
    raw_token = f"token_{uuid.uuid4().hex}"
    user_session = UserSession(
        id=uuid.uuid4(),
        user_id=user.id,
        current_business_id=biz.id,
        session_token_hash=hash_token(raw_token),
        expires_at=now + timedelta(days=7),
    )
    session.add_all([biz, user, membership, user_session])
    await session.commit()
    return biz, user, raw_token


@pytest.mark.asyncio
async def test_settings_and_services_crud(client: AsyncClient):
    """Test updating business profile, hours, services CRUD, and RBAC restrictions."""
    async with get_async_session() as session:
        biz, user, token_mgr = await create_tenant(session, "Apex Dental", f"mgr_{uuid.uuid4().hex[:6]}@example.com", role="manager")
        _, _, token_staff = await create_tenant(session, "Staff Biz", f"staff_{uuid.uuid4().hex[:6]}@example.com", role="staff")

    headers_mgr = {"Authorization": f"Bearer {token_mgr}"}
    headers_staff = {"Authorization": f"Bearer {token_staff}"}

    # 1. Update profile as manager: success
    update_data = {
        "greeting": "Apex Dental, smile with confidence!",
        "transfer_number": "+15551239999",
        "retention_days": 60,
    }
    resp = await client.put("/api/settings/profile", json=update_data, headers=headers_mgr)
    assert resp.status_code == 200
    assert resp.json()["greeting"] == "Apex Dental, smile with confidence!"
    assert resp.json()["retention_days"] == 60

    # 2. Staff cannot update profile: 403 Forbidden
    resp_staff = await client.put("/api/settings/profile", json=update_data, headers=headers_staff)
    assert resp_staff.status_code == 403

    # 3. Create Service as manager
    svc_data = {
        "name": "Composite Filling",
        "duration_minutes": 45,
        "price": 180.0,
        "description": "Tooth-colored restorative filling",
        "is_active": True,
    }
    svc_resp = await client.post("/api/settings/services", json=svc_data, headers=headers_mgr)
    assert svc_resp.status_code == 201
    created_svc = svc_resp.json()
    svc_id = created_svc["id"]
    assert created_svc["name"] == "Composite Filling"

    # 4. Update Service
    update_svc = {"price": 200.0}
    up_resp = await client.put(f"/api/settings/services/{svc_id}", json=update_svc, headers=headers_mgr)
    assert up_resp.status_code == 200
    assert up_resp.json()["price"] == 200.0

    # 5. List Services
    list_resp = await client.get("/api/settings/services", headers=headers_mgr)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 6. Delete Service (no appointments exist -> hard delete)
    del_resp = await client.delete(f"/api/settings/services/{svc_id}", headers=headers_mgr)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_knowledge_qa_and_ssrf_validation(client: AsyncClient):
    """Test manual Q&A creation, editing, deletion, and SSRF prevention on URL ingestion."""
    async with get_async_session() as session:
        biz_a, _, token_a = await create_tenant(session, "Knowledge A", f"mgr_k_{uuid.uuid4().hex[:6]}@example.com", role="manager")
        biz_b, _, token_b = await create_tenant(session, "Knowledge B", f"mgr_kb_{uuid.uuid4().hex[:6]}@example.com", role="manager")

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Create manual Q&A snippet
    qa_payload = {
        "title": "Do you accept Delta Dental?",
        "content": "Yes, we are in-network with Delta Dental Premier and PPO plans.",
    }
    qa_resp = await client.post("/api/knowledge/qa", json=qa_payload, headers=headers_a)
    assert qa_resp.status_code == 201
    doc_a = qa_resp.json()
    assert doc_a["title"] == "Do you accept Delta Dental?"
    assert doc_a["chunk_count"] >= 1

    # 2. List sources: must see doc_a
    sources_resp = await client.get("/api/knowledge/sources", headers=headers_a)
    assert sources_resp.status_code == 200
    assert len(sources_resp.json()) == 1
    assert sources_resp.json()[0]["id"] == doc_a["id"]

    # 3. Biz B cannot see or delete Biz A's doc: 404
    del_cross = await client.delete(f"/api/knowledge/sources/{doc_a['id']}", headers=headers_b)
    assert del_cross.status_code == 404

    # 4. SSRF Validation: URL ingestion must reject private / loopback IP addresses
    ssrf_payload = {"url": "http://169.254.169.254/latest/meta-data/"}
    ssrf_resp = await client.post("/api/knowledge/url", json=ssrf_payload, headers=headers_a)
    assert ssrf_resp.status_code == 400
    assert "Invalid or prohibited URL" in ssrf_resp.json()["detail"]

    # Localhost SSRF check
    local_ssrf = await client.post("/api/knowledge/url", json={"url": "http://127.0.0.1:8000/secret"}, headers=headers_a)
    assert local_ssrf.status_code == 400

    # 5. File upload validation: reject prohibited file extension
    files = {"file": ("malicious.exe", b"fake binary content", "application/octet-stream")}
    bad_upload = await client.post("/api/knowledge/upload", files=files, headers=headers_a)
    assert bad_upload.status_code == 400
    assert "Unsupported file extension" in bad_upload.json()["detail"]


@pytest.mark.asyncio
async def test_missed_questions_resolution(client: AsyncClient):
    """Test one-click resolution of knowledge misses creating Q&A and marking duplicates resolved."""
    async with get_async_session() as session:
        biz, _, token = await create_tenant(session, "Misses Dental", f"mgr_m_{uuid.uuid4().hex[:6]}@example.com", role="manager")

        miss1 = KnowledgeMiss(
            id=uuid.uuid4(),
            business_id=biz.id,
            query="Can I whiten my teeth with braces?",
            status="unresolved",
        )
        miss2 = KnowledgeMiss(
            id=uuid.uuid4(),
            business_id=biz.id,
            query="can i whiten my teeth with braces?",  # duplicate query
            status="unresolved",
        )
        session.add_all([miss1, miss2])
        await session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # Resolve miss1 with answer
    resolve_data = {
        "answer": "We recommend waiting until your braces are removed before professional whitening."
    }
    resp = await client.post(f"/api/knowledge-misses/{miss1.id}/resolve", json=resolve_data, headers=headers)
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data["status"] == "ok"
    assert res_data["resolved_count"] == 2  # Both miss1 and duplicate miss2 resolved!

    # Verify both misses are now resolved
    list_resp = await client.get("/api/knowledge-misses?status=resolved", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_appointments_manual_booking_cancel_reschedule(client: AsyncClient):
    """Test manual appointment booking, cancellation, and rescheduling with double-booking prevention."""
    now = datetime.now(timezone.utc)
    next_monday = now + timedelta(days=(7 - now.weekday()))
    slot_start = datetime(next_monday.year, next_monday.month, next_monday.day, 14, 0, tzinfo=timezone.utc)

    async with get_async_session() as session:
        biz, _, token = await create_tenant(session, "Booking Dental", f"staff_b_{uuid.uuid4().hex[:6]}@example.com", role="staff")

        svc = Service(
            id=uuid.uuid4(),
            business_id=biz.id,
            name="Oral Exam",
            duration_minutes=30,
            price=120.0,
            is_active=True,
        )
        session.add(svc)
        await session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Manual Book Appointment
    book_payload = {
        "service_id": str(svc.id),
        "customer_name": "George Miller",
        "customer_phone": "+15553337777",
        "customer_email": "george@example.com",
        "start_time": slot_start.isoformat(),
    }
    book_resp = await client.post("/api/appointments", json=book_payload, headers=headers)
    assert book_resp.status_code == 201
    appt = book_resp.json()
    appt_id = appt["id"]
    assert appt["customer_name"] == "George Miller"
    assert appt["status"] == "booked"
    assert appt["contact_id"] is not None  # Contact auto-linked

    # 2. Double-booking conflict rejection: booking same slot must fail
    conflict_payload = {
        "service_id": str(svc.id),
        "customer_name": "Other Caller",
        "customer_phone": "+15559990000",
        "start_time": slot_start.isoformat(),
    }
    conflict_resp = await client.post("/api/appointments", json=conflict_payload, headers=headers)
    assert conflict_resp.status_code == 400
    assert "already booked" in conflict_resp.json()["detail"].lower()

    # 3. Reschedule Appointment to 1 hour later
    new_slot = slot_start + timedelta(hours=1)
    resched_resp = await client.post(
        f"/api/appointments/{appt_id}/reschedule",
        json={"new_start_time": new_slot.isoformat()},
        headers=headers,
    )
    assert resched_resp.status_code == 200
    assert resched_resp.json()["status"] == "booked"

    # 4. Cancel Appointment
    cancel_resp = await client.post(f"/api/appointments/{appt_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_contacts_update_and_gdpr_delete(client: AsyncClient):
    """Test updating contact notes and owner-triggered GDPR personal data deletion."""
    async with get_async_session() as session:
        biz, owner_user, token_owner = await create_tenant(session, "GDPR Dental", f"owner_g_{uuid.uuid4().hex[:6]}@example.com", role="owner")
        _, staff_user, token_staff = await create_tenant(session, "GDPR Dental 2", f"staff_g_{uuid.uuid4().hex[:6]}@example.com", role="staff")

        contact = Contact(
            id=uuid.uuid4(),
            business_id=biz.id,
            name="John Doe",
            phone="+15558889999",
            email="johndoe@example.com",
            notes="Initial notes",
            do_not_contact=False,
        )
        call = Call(
            id=uuid.uuid4(),
            business_id=biz.id,
            contact_id=contact.id,
            caller_number="+15558889999",
            summary="Personal health details discussed in call.",
        )
        session.add_all([contact, call])
        await session.commit()

    headers_owner = {"Authorization": f"Bearer {token_owner}"}
    headers_staff = {"Authorization": f"Bearer {token_staff}"}

    # 1. Update contact notes
    up_resp = await client.put(
        f"/api/contacts/{contact.id}",
        json={"notes": "Updated VIP notes", "do_not_contact": True},
        headers=headers_owner,
    )
    assert up_resp.status_code == 200

    # 2. Staff cannot trigger GDPR data deletion: 403 Forbidden
    gdpr_staff = await client.delete(f"/api/contacts/{contact.id}/data", headers=headers_staff)
    assert gdpr_staff.status_code == 403

    # 3. Owner triggers GDPR data deletion
    gdpr_owner = await client.delete(f"/api/contacts/{contact.id}/data", headers=headers_owner)
    assert gdpr_owner.status_code == 200
    assert "successfully scrubbed" in gdpr_owner.json()["message"]


@pytest.mark.asyncio
async def test_background_worker_retention_job():
    """Test background job queue execution with the worker runner."""
    async with get_async_session() as session:
        biz = Business(
            id=uuid.uuid4(),
            name="Worker Test Biz",
            business_type="Dental",
            timezone="UTC",
            greeting="Hello",
            tone="warm",
            retention_days=30,
        )
        session.add(biz)
        await session.flush()

        job = Job(
            id=uuid.uuid4(),
            business_id=biz.id,
            type="retention_cleanup",
            status="pending",
            payload={},
        )
        session.add(job)
        await session.commit()
        job_id = job.id

    # Execute background worker
    async with get_async_session() as session:
        processed_job = await process_next_job(session)
        assert processed_job is not None
        assert processed_job.id == job_id
        assert processed_job.status == "completed"
        assert processed_job.progress == 100
