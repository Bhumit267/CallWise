"""Helper script to deterministically create testing accounts across tenants.

Creates owner, manager, and staff test users for Aarav Health & Dental Clinic
and Luxe Glow Salon & Spa with known Argon2id hashed passwords.
Safe and idempotent: updates passwords and memberships if accounts already exist.
"""

import asyncio
from datetime import datetime, timezone
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from callwise.api.security import hash_password
from callwise.db.models import Business, Membership, User
from callwise.db.session import AsyncSessionLocal

# Seeded Demo Businesses
INDIAN_CLINIC_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
SALON_BIZ_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
# Backward-compatibility alias
DENTAL_BIZ_ID = INDIAN_CLINIC_ID

TEST_USERS = [
    # --- Tenant 1: Aarav Health & Dental Clinic (Bengaluru, India) ---
    {
        "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000001"),
        "email": "aarav.owner@test.com",
        "name": "Dr. Aarav Sharma",
        "password": "Password123!",
        "business_id": INDIAN_CLINIC_ID,
        "role": "owner",
    },
    {
        "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000002"),
        "email": "aarav.manager@test.com",
        "name": "Dr. Priya Nair",
        "password": "Password123!",
        "business_id": INDIAN_CLINIC_ID,
        "role": "manager",
    },
    {
        "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000003"),
        "email": "aarav.staff@test.com",
        "name": "Neha Frontdesk",
        "password": "Password123!",
        "business_id": INDIAN_CLINIC_ID,
        "role": "staff",
    },
    # --- Tenant 2: Luxe Glow Salon & Spa (Los Angeles, USA) ---
    {
        "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000001"),
        "email": "salon.owner@test.com",
        "name": "Chloe Glow",
        "password": "Password123!",
        "business_id": SALON_BIZ_ID,
        "role": "owner",
    },
    {
        "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000002"),
        "email": "salon.manager@test.com",
        "name": "Mike Stylist",
        "password": "Password123!",
        "business_id": SALON_BIZ_ID,
        "role": "manager",
    },
    {
        "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000003"),
        "email": "salon.staff@test.com",
        "name": "Samantha Assistant",
        "password": "Password123!",
        "business_id": SALON_BIZ_ID,
        "role": "staff",
    },
]


async def seed_test_accounts():
    print("=== Seeding Manual Testing Accounts ===")
    async with AsyncSessionLocal() as session:
        # Verify businesses exist
        clinic = await session.get(Business, INDIAN_CLINIC_ID)
        salon = await session.get(Business, SALON_BIZ_ID)

        if not clinic or not salon:
            print("ERROR: Seeded demo businesses not found. Please run 'uv run python -m callwise.cli seed' first.")
            return

        for u_data in TEST_USERS:
            # Check if user exists by email
            stmt = select(User).where(User.email == u_data["email"]).options(selectinload(User.memberships))
            user = (await session.execute(stmt)).scalar_one_or_none()

            pwd_hash = hash_password(u_data["password"])

            if not user:
                user = User(
                    id=u_data["id"],
                    email=u_data["email"],
                    name=u_data["name"],
                    password_hash=pwd_hash,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                print(f"[CREATED] User: {user.email} (Name: {user.name})")
            else:
                user.name = u_data["name"]
                user.password_hash = pwd_hash
                user.is_active = True
                await session.flush()
                print(f"[UPDATED] User: {user.email}")

            # Verify or create membership
            m_stmt = select(Membership).where(
                Membership.user_id == user.id,
                Membership.business_id == u_data["business_id"],
            )
            membership = (await session.execute(m_stmt)).scalar_one_or_none()

            if not membership:
                membership = Membership(
                    user_id=user.id,
                    business_id=u_data["business_id"],
                    role=u_data["role"],
                )
                session.add(membership)
                await session.flush()
                print(f"  └─ Added membership: {u_data['role']} in {u_data['business_id']}")
            else:
                membership.role = u_data["role"]
                await session.flush()
                print(f"  └─ Updated membership: {u_data['role']}")

        await session.commit()
    print("=== Test Accounts Seeded Successfully ===")


if __name__ == "__main__":
    asyncio.run(seed_test_accounts())
