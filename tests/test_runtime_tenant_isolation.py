"""Runtime Tenant Isolation and Cross-Tenant Security Verification Test Suite.

Verifies tenant isolation at runtime over HTTP using the running application's
normal database connection pool (WITHOUT any manual 'SET ROLE callwise_app' fixture backdoor).

Covers:
1. Bidirectional URL path-parameter cross-tenant attacks (Aarav attacking Luxe, Luxe attacking Aarav).
2. Role-based testing across Owner, Manager, and Staff roles.
3. Automated OpenAPI path-parameter audit: ensures 100% of parameterized routes are tested.
4. Body-supplied foreign IDs (e.g. foreign service_id, foreign contact_id, foreign assigned_to_user_id).
5. Cross-tenant phone number collision behavior.
"""

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Dict, List, Set, Tuple
import uuid
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from callwise.api.main import app
from callwise.api.security import auth_rate_limiter, hash_password, hash_token
from callwise.db.models import (
    Appointment,
    AuditLog,
    Business,
    Call,
    CallTurn,
    Contact,
    Document,
    FollowUp,
    Invite,
    Job,
    KnowledgeMiss,
    Membership,
    Message,
    PhoneNumber,
    Service,
    Session as UserSession,
    UsageRecord,
    User,
    WidgetSettings,
)
from callwise.db.session import async_engine, get_async_session, get_sync_session

TENANT_A_BIZ_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")  # Aarav Clinic
TENANT_B_BIZ_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")  # Luxe Glow Salon


@pytest_asyncio.fixture(autouse=True)
async def cleanup():
    """Reset rate limiter and ensure seed data exists in test DB."""
    auth_rate_limiter.clear_all()
    with get_sync_session() as sync_session:
        from callwise.db.seed import seed_businesses
        seed_businesses(sync_session)
        sync_session.commit()
    from scripts.testing.seed_test_accounts import seed_test_accounts
    await seed_test_accounts()
    yield
    auth_rate_limiter.clear_all()
    await async_engine.dispose()


@pytest_asyncio.fixture
async def client():
    """Async HTTP test client bound to FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def ensure_tenant_resources(biz_id: uuid.UUID) -> Dict[str, uuid.UUID]:
    """Ensure a tenant has at least one active record for every resource type."""
    now = datetime.now(timezone.utc)
    res_ids = {}

    async with get_async_session() as session:
        # 1. Contact
        c = (
            await session.execute(
                select(Contact).where(Contact.business_id == biz_id)
            )
        ).scalars().first()
        if not c:
            c = Contact(
                id=uuid.uuid4(),
                business_id=biz_id,
                name=f"Customer for {biz_id}",
                phone=f"+1555{uuid.uuid4().hex[:7]}",
                email=f"customer_{biz_id.hex[:6]}@test.com",
            )
            session.add(c)
            await session.flush()
        res_ids["contact_id"] = c.id

        # 2. Service
        s = (
            await session.execute(
                select(Service).where(Service.business_id == biz_id)
            )
        ).scalars().first()
        if not s:
            s = Service(
                id=uuid.uuid4(),
                business_id=biz_id,
                name=f"Service for {biz_id}",
                duration_minutes=30,
                price=50.0,
            )
            session.add(s)
            await session.flush()
        res_ids["service_id"] = s.id

        # 3. Call
        call = (
            await session.execute(
                select(Call).where(Call.business_id == biz_id)
            )
        ).scalars().first()
        if not call:
            call = Call(
                id=uuid.uuid4(),
                business_id=biz_id,
                contact_id=c.id,
                caller_number="+15552220001",
                started_at=now - timedelta(hours=1),
                duration_seconds=120.0,
                summary="Confidential call transcript",
            )
            session.add(call)
            await session.flush()
        res_ids["call_id"] = call.id

        # 4. Message
        msg = (
            await session.execute(
                select(Message).where(Message.business_id == biz_id)
            )
        ).scalars().first()
        if not msg:
            msg = Message(
                id=uuid.uuid4(),
                business_id=biz_id,
                call_id=call.id,
                contact_id=c.id,
                caller_name="Caller",
                callback_number="+15552220099",
                reason="Confidential callback message",
            )
            session.add(msg)
            await session.flush()
        res_ids["message_id"] = msg.id

        # 5. Appointment
        appt = (
            await session.execute(
                select(Appointment).where(Appointment.business_id == biz_id)
            )
        ).scalars().first()
        if not appt:
            appt = Appointment(
                id=uuid.uuid4(),
                business_id=biz_id,
                service_id=s.id,
                contact_id=c.id,
                customer_name="Patient/Client",
                customer_phone="+15552220001",
                start_at=now + timedelta(days=2),
                end_at=now + timedelta(days=2, minutes=30),
                status="booked",
                booking_code_hash=hash_token("TEST1234"),
            )
            session.add(appt)
            await session.flush()
        res_ids["appointment_id"] = appt.id

        # 6. Follow-up
        fu = (
            await session.execute(
                select(FollowUp).where(FollowUp.business_id == biz_id)
            )
        ).scalars().first()
        if not fu:
            fu = FollowUp(
                id=uuid.uuid4(),
                business_id=biz_id,
                contact_id=c.id,
                title="Internal Secret Task",
                description="Confidential follow-up task",
                source="manual",
                status="open",
            )
            session.add(fu)
            await session.flush()
        res_ids["follow_up_id"] = fu.id

        # 7. Document
        doc = (
            await session.execute(
                select(Document).where(Document.business_id == biz_id)
            )
        ).scalars().first()
        if not doc:
            doc = Document(
                id=uuid.uuid4(),
                business_id=biz_id,
                title="Confidential Policy",
                source_type="text",
                source_uri="text://internal",
            )
            session.add(doc)
            await session.flush()
        res_ids["document_id"] = doc.id

        # 8. Knowledge Miss
        km = (
            await session.execute(
                select(KnowledgeMiss).where(KnowledgeMiss.business_id == biz_id)
            )
        ).scalars().first()
        if not km:
            km = KnowledgeMiss(
                id=uuid.uuid4(),
                business_id=biz_id,
                call_id=call.id,
                query="Confidential question query",
                status="unresolved",
            )
            session.add(km)
            await session.flush()
        res_ids["miss_id"] = km.id

        # 9. Phone Number
        pn = (
            await session.execute(
                select(PhoneNumber).where(PhoneNumber.business_id == biz_id)
            )
        ).scalars().first()
        if not pn:
            # Deterministic purely numeric 10-digit number
            digits = "".join([str(int(c, 16) % 10) for c in uuid.uuid4().hex[:7]])
            pn = PhoneNumber(
                id=uuid.uuid4(),
                business_id=biz_id,
                e164_number=f"+1555{digits}",
                provider="livekit",
                label="Inbound Support",
                is_active=True,
            )
            session.add(pn)
            await session.flush()
        res_ids["phone_id"] = pn.id

        # 10. Team Member (Membership)
        mem = (
            await session.execute(
                select(Membership).where(
                    Membership.business_id == biz_id,
                    Membership.role == "staff",
                )
            )
        ).scalars().first()
        if not mem:
            mem = (
                await session.execute(
                    select(Membership).where(Membership.business_id == biz_id)
                )
            ).scalars().first()
        res_ids["member_user_id"] = mem.user_id

        # 11. Invite
        inv = (
            await session.execute(
                select(Invite).where(Invite.business_id == biz_id)
            )
        ).scalars().first()
        if not inv:
            inv = Invite(
                id=uuid.uuid4(),
                business_id=biz_id,
                email=f"pending_{biz_id.hex[:6]}@test.com",
                role="staff",
                token_hash=uuid.uuid4().hex,
                expires_at=now + timedelta(days=5),
            )
            session.add(inv)
            await session.flush()
        res_ids["invite_id"] = inv.id

        # 12. Job (Knowledge / Background)
        j = (
            await session.execute(
                select(Job).where(Job.business_id == biz_id)
            )
        ).scalars().first()
        if not j:
            j = Job(
                id=uuid.uuid4(),
                business_id=biz_id,
                type="document_ingestion",
                status="pending",
                payload={"file": "test.txt"},
                progress=0,
            )
            session.add(j)
            await session.flush()
        res_ids["job_id"] = j.id

        # 13. Audit Log
        al = (
            await session.execute(
                select(AuditLog).where(AuditLog.business_id == biz_id)
            )
        ).scalars().first()
        if not al:
            al = AuditLog(
                id=uuid.uuid4(),
                business_id=biz_id,
                user_id=mem.user_id,
                action="test_action",
                resource_type="test",
                resource_id="1",
                changes={"secret": "confidential"},
            )
            session.add(al)
            await session.flush()
        res_ids["audit_id"] = al.id

        # 14. Widget Settings
        ws = (
            await session.execute(
                select(WidgetSettings).where(WidgetSettings.business_id == biz_id)
            )
        ).scalars().first()
        if not ws:
            ws = WidgetSettings(
                id=uuid.uuid4(),
                business_id=biz_id,
                public_key=f"cw_live_{uuid.uuid4().hex[:16]}",
                is_enabled=True,
                allowed_origins="*",
            )
            session.add(ws)
            await session.flush()
        res_ids["public_key"] = ws.public_key

        await session.commit()

    return res_ids


def get_all_openapi_id_routes() -> List[Tuple[str, str, str]]:
    """
    Extract all authenticated OpenAPI routes that contain a path parameter like {id}.
    Returns list of tuples: (method, path, param_name).
    """
    schema = app.openapi()
    routes = []
    # Public endpoints that contain path params but are unauthenticated / widget
    PUBLIC_PARAM_ROUTES = {"/api/widget/config/{public_key}"}

    for path, path_item in schema["paths"].items():
        if path in PUBLIC_PARAM_ROUTES:
            continue
        params = re.findall(r"\{(\w+)\}", path)
        if params:
            param_name = params[0]
            for method in path_item.keys():
                if method.lower() in ("get", "post", "put", "patch", "delete"):
                    routes.append((method.upper(), path, param_name))

    return sorted(routes, key=lambda x: (x[1], x[0]))


def build_route_matrix(resources: Dict[str, uuid.UUID]) -> List[Tuple[str, str, Any, str]]:
    """Build concrete test cases for all parameterized routes using a target tenant's resource IDs."""
    return [
        ("GET", f"/api/calls/{resources['call_id']}", None, "Call detail"),
        ("GET", f"/api/messages/{resources['message_id']}", None, "Message detail"),
        ("GET", f"/api/appointments/{resources['appointment_id']}", None, "Appointment detail"),
        ("POST", f"/api/appointments/{resources['appointment_id']}/cancel", {}, "Appointment cancel"),
        ("POST", f"/api/appointments/{resources['appointment_id']}/reschedule", {"new_start_time": "2026-11-20T10:00:00Z"}, "Appointment reschedule"),
        ("GET", f"/api/contacts/{resources['contact_id']}", None, "Contact detail"),
        ("PUT", f"/api/contacts/{resources['contact_id']}", {"notes": "Malicious edit"}, "Contact update"),
        ("DELETE", f"/api/contacts/{resources['contact_id']}/data", None, "Contact GDPR delete"),
        ("GET", f"/api/follow-ups/{resources['follow_up_id']}", None, "Follow-up detail"),
        ("PATCH", f"/api/follow-ups/{resources['follow_up_id']}", {"title": "Malicious rename"}, "Follow-up update"),
        ("DELETE", f"/api/knowledge/sources/{resources['document_id']}", None, "Knowledge source delete"),
        ("POST", f"/api/knowledge/sources/{resources['document_id']}/reingest", None, "Knowledge source reingest"),
        ("PUT", f"/api/knowledge/qa/{resources['document_id']}", {"content": "Malicious Q&A"}, "Knowledge Q&A update"),
        ("GET", f"/api/knowledge/jobs/{resources['job_id']}", None, "Knowledge job status"),
        ("POST", f"/api/knowledge-misses/{resources['miss_id']}/resolve", {"answer": "Hacked answer"}, "Knowledge miss resolve"),
        ("POST", f"/api/knowledge-misses/{resources['miss_id']}/ignore", None, "Knowledge miss ignore"),
        ("PUT", f"/api/settings/services/{resources['service_id']}", {"name": "Hacked Service", "duration_minutes": 15, "price": 1.0}, "Service update"),
        ("DELETE", f"/api/settings/services/{resources['service_id']}", None, "Service delete"),
        ("DELETE", f"/api/phone-numbers/{resources['phone_id']}", None, "Phone number delete"),
        ("PATCH", f"/api/team/members/{resources['member_user_id']}", {"role": "owner"}, "Team member role update"),
        ("DELETE", f"/api/team/members/{resources['member_user_id']}", None, "Team member remove"),
        ("DELETE", f"/api/team/invites/{resources['invite_id']}", None, "Team invite revoke"),
    ]


@pytest.mark.asyncio
async def test_openapi_id_routes_full_coverage():
    """
    Enforce that 100% of OpenAPI routes taking a path parameter are covered in our test matrix.
    If a new parameterized route is added to Callwise, this test will fail until it is included.
    """
    openapi_routes = get_all_openapi_id_routes()
    dummy_resources = {
        "call_id": uuid.uuid4(),
        "message_id": uuid.uuid4(),
        "appointment_id": uuid.uuid4(),
        "contact_id": uuid.uuid4(),
        "follow_up_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "job_id": uuid.uuid4(),
        "miss_id": uuid.uuid4(),
        "service_id": uuid.uuid4(),
        "phone_id": uuid.uuid4(),
        "member_user_id": uuid.uuid4(),
        "invite_id": uuid.uuid4(),
    }
    matrix = build_route_matrix(dummy_resources)

    # Normalize patterns from matrix by replacing dummy UUIDs with {param}
    covered_patterns: Set[Tuple[str, str]] = set()
    uuid_regex = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

    for method, path, _, _ in matrix:
        normalized_path = re.sub(uuid_regex, "{id}", path)
        covered_patterns.add((method, normalized_path))

    missing_routes = []
    for method, path, param in openapi_routes:
        normalized_openapi_path = re.sub(r"\{" + param + r"\}", "{id}", path)
        if (method, normalized_openapi_path) not in covered_patterns:
            missing_routes.append(f"{method} {path}")

    assert len(missing_routes) == 0, (
        f"CRITICAL: Uncovered parameterized OpenAPI routes found in schema! Add them to isolation matrix:\n"
        + "\n".join(missing_routes)
    )
    print(f"\n[OK] 100% of parameterized OpenAPI routes ({len(openapi_routes)} endpoints) are actively covered.")


@pytest.mark.asyncio
async def test_bidirectional_and_role_based_isolation(client: AsyncClient):
    """
    Run the entire parameterized route matrix:
    1. Aarav attacking Luxe (Owner, Manager, Staff roles).
    2. Luxe attacking Aarav (Owner, Manager, Staff roles).
    Every cross-tenant request must return 403 or 404.
    """
    from callwise.config import settings
    active_db = settings.database_url.rpartition("/")[-1]
    print(f"\n=======================================================")
    print(f" Active Test Database Connection: [{active_db}]")
    print(f"=======================================================")
    assert active_db.endswith("_test"), f"Safety check failed: active DB '{active_db}' is not a test DB!"

    aarav_resources = await ensure_tenant_resources(TENANT_A_BIZ_ID)
    luxe_resources = await ensure_tenant_resources(TENANT_B_BIZ_ID)

    # Test matrix combinations: (Attacker email, Target Tenant Name, Target Resources)
    scenarios = [
        # Aarav -> Luxe
        ("aarav.owner@test.com", "Aarav Owner", "Luxe Glow Salon", luxe_resources),
        ("aarav.manager@test.com", "Aarav Manager", "Luxe Glow Salon", luxe_resources),
        ("aarav.staff@test.com", "Aarav Staff", "Luxe Glow Salon", luxe_resources),
        # Luxe -> Aarav
        ("salon.owner@test.com", "Luxe Owner", "Aarav Dental Clinic", aarav_resources),
        ("salon.manager@test.com", "Luxe Manager", "Aarav Dental Clinic", aarav_resources),
        ("salon.staff@test.com", "Luxe Staff", "Aarav Dental Clinic", aarav_resources),
    ]

    total_probes = 0
    failures = []

    for email, role_name, target_name, target_resources in scenarios:
        login_res = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
        csrf_token = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token}

        matrix = build_route_matrix(target_resources)
        print(f"\n--- Testing Scenario: [{role_name}] attacking [{target_name}] ({len(matrix)} routes) ---")

        for method, path, body, desc in matrix:
            total_probes += 1
            if method == "GET":
                resp = await client.get(path)
            elif method == "POST":
                resp = await client.post(path, json=body or {}, headers=headers)
            elif method == "PUT":
                resp = await client.put(path, json=body or {}, headers=headers)
            elif method == "PATCH":
                resp = await client.patch(path, json=body or {}, headers=headers)
            elif method == "DELETE":
                resp = await client.delete(path, headers=headers)

            status_code = resp.status_code
            # Staff/Manager might get 403 on Owner endpoints, or 404 because cross-tenant row doesn't exist
            is_blocked = status_code in (403, 404)
            if not is_blocked:
                failures.append(f"LEAK: [{role_name}] on {method} {path} returned {status_code} ({resp.text})")

        # Logout before next scenario
        await client.post("/api/auth/logout", headers=headers)

    print(f"\n[OK] Executed {total_probes} cross-tenant probes across 6 tenant-role permutations.")
    assert len(failures) == 0, f"Cross-tenant leaks detected!\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_body_supplied_foreign_ids_isolation(client: AsyncClient):
    """
    Test create/update endpoints that accept an ID in the request body across both directions
    (Aarav attacking Luxe AND Luxe attacking Aarav) and across Owner, Manager, and Staff roles:
    1. POST /api/appointments with foreign service_id (expect 404)
    2. POST /api/follow-ups with foreign contact_id (expect 404)
    3. POST /api/follow-ups with foreign assigned_to_user_id (expect 404)
    4. PATCH /api/follow-ups/{own_id} with foreign assigned_to_user_id (expect 404)
    5. POST /api/onboarding/test-agent with foreign call_id (expect 404)
    6. POST /api/widget/chat with foreign call_id (expect 404)
    7. POST /api/widget/lead with foreign call_id (expect 404)
    8. POST /api/auth/switch-business with foreign business_id (expect 403)

    Verifies that nothing is created or modified in either tenant.
    """
    aarav_resources = await ensure_tenant_resources(TENANT_A_BIZ_ID)
    luxe_resources = await ensure_tenant_resources(TENANT_B_BIZ_ID)

    # Initial counts
    async with get_async_session() as session:
        fu_count_start = (await session.execute(select(func.count(FollowUp.id)))).scalar()
        appt_count_start = (await session.execute(select(func.count(Appointment.id)))).scalar()
        call_count_start = (await session.execute(select(func.count(Call.id)))).scalar()

    directions = [
        # (attacker_business, target_business, attacker_accounts, target_resources, attacker_resources)
        (
            "Aarav -> Luxe",
            [
                ("aarav.owner@test.com", "Owner"),
                ("aarav.manager@test.com", "Manager"),
                ("aarav.staff@test.com", "Staff"),
            ],
            luxe_resources,
            aarav_resources,
            TENANT_B_BIZ_ID,
        ),
        (
            "Luxe -> Aarav",
            [
                ("salon.owner@test.com", "Owner"),
                ("salon.manager@test.com", "Manager"),
                ("salon.staff@test.com", "Staff"),
            ],
            aarav_resources,
            luxe_resources,
            TENANT_A_BIZ_ID,
        ),
    ]

    failures = []

    for dir_label, accounts, target_res, attacker_res, target_biz_id in directions:
        for email, role in accounts:
            print(f"\n--- Testing Body-Supplied IDs: [{dir_label}] as [{role}] ({email}) ---")
            login_res = await client.post(
                "/api/auth/login",
                json={"email": email, "password": "Password123!"},
            )
            assert login_res.status_code == 200, f"Login failed for {email}: {login_res.text}"
            csrf_token = login_res.json()["csrf_token"]
            headers = {"X-CSRF-Token": csrf_token}

            # 1. POST /api/appointments with foreign service_id (Staff/Manager/Owner allowed)
            res_appt = await client.post(
                "/api/appointments",
                json={
                    "service_id": str(target_res["service_id"]),
                    "customer_name": "Intruder Patient",
                    "customer_phone": "+15559998888",
                    "start_time": "2026-11-25T14:00:00Z",
                },
                headers=headers,
            )
            print(f" [{role}] POST /api/appointments (foreign service_id) -> HTTP {res_appt.status_code}")
            if res_appt.status_code != 404:
                failures.append(f"[{dir_label}][{role}] POST /api/appointments foreign service_id returned {res_appt.status_code} (expected 404)")

            # 2. POST /api/follow-ups with foreign contact_id (Staff/Manager/Owner allowed)
            res_fu_contact = await client.post(
                "/api/follow-ups",
                json={
                    "title": "Cross Tenant Followup Probe",
                    "contact_id": str(target_res["contact_id"]),
                },
                headers=headers,
            )
            print(f" [{role}] POST /api/follow-ups (foreign contact_id) -> HTTP {res_fu_contact.status_code}")
            if res_fu_contact.status_code != 404:
                failures.append(f"[{dir_label}][{role}] POST /api/follow-ups foreign contact_id returned {res_fu_contact.status_code} (expected 404)")

            # 3. POST /api/follow-ups with foreign assigned_to_user_id (Staff/Manager/Owner allowed)
            res_fu_user = await client.post(
                "/api/follow-ups",
                json={
                    "title": "Cross Tenant Assign Probe",
                    "assigned_to_user_id": str(target_res["member_user_id"]),
                },
                headers=headers,
            )
            print(f" [{role}] POST /api/follow-ups (foreign assigned_to_user_id) -> HTTP {res_fu_user.status_code}")
            if res_fu_user.status_code != 404:
                failures.append(f"[{dir_label}][{role}] POST /api/follow-ups foreign assigned_to_user_id returned {res_fu_user.status_code} (expected 404)")

            # 4. PATCH /api/follow-ups/{own_id} with foreign assigned_to_user_id (Staff/Manager/Owner allowed)
            own_fu_id = attacker_res["follow_up_id"]
            res_fu_patch = await client.patch(
                f"/api/follow-ups/{own_fu_id}",
                json={"assigned_to_user_id": str(target_res["member_user_id"])},
                headers=headers,
            )
            print(f" [{role}] PATCH /api/follow-ups/{own_fu_id} (foreign assigned_to_user_id) -> HTTP {res_fu_patch.status_code}")
            if res_fu_patch.status_code != 404:
                failures.append(f"[{dir_label}][{role}] PATCH /api/follow-ups foreign assigned_to_user_id returned {res_fu_patch.status_code} (expected 404)")

            # 5. POST /api/onboarding/test-agent with foreign call_id (Staff/Manager/Owner allowed)
            res_test_agent = await client.post(
                "/api/onboarding/test-agent",
                json={
                    "message": "Hello cross tenant probe",
                    "call_id": str(target_res["call_id"]),
                },
                headers=headers,
            )
            print(f" [{role}] POST /api/onboarding/test-agent (foreign call_id) -> HTTP {res_test_agent.status_code}")
            if res_test_agent.status_code != 404:
                failures.append(f"[{dir_label}][{role}] POST /api/onboarding/test-agent foreign call_id returned {res_test_agent.status_code} (expected 404)")

            # 6. POST /api/auth/switch-business with foreign business_id
            res_switch = await client.post(
                "/api/auth/switch-business",
                json={"business_id": str(target_biz_id)},
                headers=headers,
            )
            print(f" [{role}] POST /api/auth/switch-business (foreign business_id) -> HTTP {res_switch.status_code}")
            if res_switch.status_code != 403:
                failures.append(f"[{dir_label}][{role}] POST /api/auth/switch-business returned {res_switch.status_code} (expected 403)")

            await client.post("/api/auth/logout", headers=headers)

        # 7. Public Widget Endpoints: chat & lead with foreign call_id
        # Uses attacker tenant's public_key, but supplies target tenant's call_id
        res_widget_chat = await client.post(
            "/api/widget/chat",
            json={
                "public_key": attacker_res["public_key"],
                "message": "Testing cross-tenant session attach",
                "call_id": str(target_res["call_id"]),
            },
        )
        print(f" [Widget] POST /api/widget/chat (foreign call_id) -> HTTP {res_widget_chat.status_code}")
        if res_widget_chat.status_code != 404:
            failures.append(f"[{dir_label}] POST /api/widget/chat foreign call_id returned {res_widget_chat.status_code} (expected 404)")

        res_widget_lead = await client.post(
            "/api/widget/lead",
            json={
                "public_key": attacker_res["public_key"],
                "name": "Widget Intruder",
                "email": "intruder@test.com",
                "phone": "+15558887777",
                "call_id": str(target_res["call_id"]),
            },
        )
        print(f" [Widget] POST /api/widget/lead (foreign call_id) -> HTTP {res_widget_lead.status_code}")
        if res_widget_lead.status_code != 404:
            failures.append(f"[{dir_label}] POST /api/widget/lead foreign call_id returned {res_widget_lead.status_code} (expected 404)")

    # Verify zero side-effects in DB
    async with get_async_session() as session:
        fu_count_end = (await session.execute(select(func.count(FollowUp.id)))).scalar()
        appt_count_end = (await session.execute(select(func.count(Appointment.id)))).scalar()
        call_count_end = (await session.execute(select(func.count(Call.id)))).scalar()

    assert fu_count_end == fu_count_start, f"Follow-up records leaked into DB! ({fu_count_start} -> {fu_count_end})"
    assert appt_count_end == appt_count_start, f"Appointment records leaked into DB! ({appt_count_start} -> {appt_count_end})"
    assert call_count_end == call_count_start, f"Call records leaked into DB! ({call_count_start} -> {call_count_end})"

    assert len(failures) == 0, f"Body-supplied foreign ID leaks detected!\n" + "\n".join(failures)
    print("\n[OK] All body-supplied foreign ID probes correctly rejected with HTTP 404/403 with zero side-effects.")


@pytest.mark.asyncio
async def test_phone_number_cross_tenant_collision(client: AsyncClient):
    """
    Test phone number collision bidirectionally:
    1. Aarav Owner and Manager attempt to register Luxe's phone number -> expect 409
    2. Luxe Owner and Manager attempt to register Aarav's phone number -> expect 409
    Verify:
    - Status code is strictly 409 Conflict.
    - Error detail is generic 'This phone number is not available.' with zero leak of tenant metadata.
    - Session remains healthy and usable after the transaction rollback.
    """
    aarav_resources = await ensure_tenant_resources(TENANT_A_BIZ_ID)
    luxe_resources = await ensure_tenant_resources(TENANT_B_BIZ_ID)

    async with get_async_session() as session:
        luxe_pn = (
            await session.execute(
                select(PhoneNumber).where(PhoneNumber.business_id == TENANT_B_BIZ_ID)
            )
        ).scalars().first()
        aarav_pn = (
            await session.execute(
                select(PhoneNumber).where(PhoneNumber.business_id == TENANT_A_BIZ_ID)
            )
        ).scalars().first()
        assert luxe_pn is not None
        assert aarav_pn is not None
        luxe_number = luxe_pn.e164_number
        aarav_number = aarav_pn.e164_number

    test_cases = [
        ("Aarav Owner -> Luxe number", "aarav.owner@test.com", luxe_number, "Luxe", str(TENANT_B_BIZ_ID)),
        ("Aarav Manager -> Luxe number", "aarav.manager@test.com", luxe_number, "Luxe", str(TENANT_B_BIZ_ID)),
        ("Luxe Owner -> Aarav number", "salon.owner@test.com", aarav_number, "Aarav", str(TENANT_A_BIZ_ID)),
        ("Luxe Manager -> Aarav number", "salon.manager@test.com", aarav_number, "Aarav", str(TENANT_A_BIZ_ID)),
    ]

    for label, email, colliding_number, victim_name, victim_id in test_cases:
        print(f"\n--- Testing Phone Collision: [{label}] ---")
        login_res = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "Password123!"},
        )
        assert login_res.status_code == 200
        csrf_token = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf_token}

        res = await client.post(
            "/api/phone-numbers",
            json={
                "e164_number": colliding_number,
                "provider": "livekit",
                "label": "Colliding Inbound",
            },
            headers=headers,
        )

        print(f" Status Code:   {res.status_code}")
        print(f" Response Body: {res.text}")

        assert res.status_code == 409, f"[{label}] Expected HTTP 409, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("detail") == "This phone number is not available.", f"[{label}] Unexpected error detail: {data}"

        # Ensure no information disclosure of victim tenant
        assert victim_name.lower() not in res.text.lower(), f"[{label}] Leaked victim tenant name in response!"
        assert victim_id not in res.text, f"[{label}] Leaked victim tenant business_id in response!"

        # Verify session usability after rollback
        list_res = await client.get("/api/phone-numbers", headers=headers)
        assert list_res.status_code == 200, f"[{label}] Session unusable after rollback: {list_res.text}"

        await client.post("/api/auth/logout", headers=headers)

    print("\n[OK] Phone collision correctly returns 409, leaks zero metadata, and session remains fully usable.")
