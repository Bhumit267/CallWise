"""Reduce database to exactly two demo businesses: Aarav Health & Dental Clinic and Luxe Glow Salon & Spa."""

import argparse
import sys
import uuid
from urllib.parse import urlparse
import psycopg
from tabulate import tabulate

FK_TABLES = [
    ("appointments", "business_id"),
    ("audit_log", "business_id"),
    ("blocklist", "business_id"),
    ("call_turns", "business_id"),
    ("calls", "business_id"),
    ("chunks", "business_id"),
    ("contacts", "business_id"),
    ("documents", "business_id"),
    ("follow_ups", "business_id"),
    ("invites", "business_id"),
    ("jobs", "business_id"),
    ("knowledge_misses", "business_id"),
    ("memberships", "business_id"),
    ("messages", "business_id"),
    ("notifications", "business_id"),
    ("phone_numbers", "business_id"),
    ("reminders", "business_id"),
    ("services", "business_id"),
    ("sessions", "current_business_id"),
    ("transfers", "business_id"),
    ("usage_limits", "business_id"),
    ("usage_records", "business_id"),
    ("verification_attempts", "business_id"),
    ("widget_settings", "business_id"),
]

KEPT_IDS = [
    uuid.UUID("33333333-3333-3333-3333-333333333333"),  # Aarav Health & Dental Clinic
    uuid.UUID("22222222-2222-2222-2222-222222222222"),  # Luxe Glow Salon & Spa
]
KEPT_IDS_STR = ", ".join(f"'{k}'" for k in KEPT_IDS)


def get_table_counts(conn, target_db: str) -> dict:
    counts = {}
    with conn.cursor() as cur:
        # Total businesses
        cur.execute("SELECT count(*) FROM businesses;")
        counts["businesses_total"] = cur.fetchone()[0]

        # Foreign / unkept businesses
        cur.execute(f"SELECT count(*) FROM businesses WHERE id NOT IN ({KEPT_IDS_STR});")
        counts["businesses_unkept"] = cur.fetchone()[0]

        # Total users
        cur.execute("SELECT count(*) FROM users;")
        counts["users_total"] = cur.fetchone()[0]

        # Orphaned users (no active memberships)
        cur.execute("SELECT count(*) FROM users u LEFT JOIN memberships m ON u.id = m.user_id WHERE m.id IS NULL;")
        counts["users_orphaned"] = cur.fetchone()[0]

        # All 24 FK child tables
        for tbl, col in FK_TABLES:
            cur.execute(f"SELECT count(*) FROM {tbl};")
            total = cur.fetchone()[0]
            cur.execute(f"SELECT count(*) FROM {tbl} WHERE {col} IS NOT NULL AND {col} NOT IN ({KEPT_IDS_STR});")
            unkept = cur.fetchone()[0]
            counts[tbl] = {"total": total, "unkept": unkept}

    return counts


def run_reduction(db_url: str, confirm: bool = False):
    parsed = urlparse(db_url)
    target_host = f"{parsed.hostname or 'localhost'}:{parsed.port or 5432}"
    target_db = parsed.path.lstrip("/").split("?")[0]

    print(f"\n=======================================================")
    print(f" Target Host:     [{target_host}]")
    print(f" Target Database: [{target_db}]")
    print(f"=======================================================\n")

    # Safety check 1: Allowed databases
    allowed_dbs = ["callwise", "callwise_scratch"]
    if target_db not in allowed_dbs:
        print(f"❌ SAFETY ABORT: Refusing to run on database '{target_db}'. Allowed databases: {allowed_dbs}")
        sys.exit(1)

    # Safety check 2: Explicit confirmation required for development database 'callwise'
    if target_db == "callwise" and not confirm:
        print("❌ SAFETY ABORT: Refusing to run on development database 'callwise' without explicit --confirm flag.")
        sys.exit(1)

    with psycopg.connect(db_url, autocommit=False) as conn:
        # 1. Collect Before Counts
        print(f"[{target_db}] Collecting before-counts...")
        before = get_table_counts(conn, target_db)

        # 2. Delete unwanted businesses
        with conn.cursor() as cur:
            cur.execute(f"SELECT id, name FROM businesses WHERE id NOT IN ({KEPT_IDS_STR});")
            to_delete = cur.fetchall()
            print(f"[{target_db}] Found {len(to_delete)} businesses to delete:")
            for b_id, b_name in to_delete:
                print(f"  - Deleting business: {b_name} ({b_id})")

            cur.execute(f"DELETE FROM businesses WHERE id NOT IN ({KEPT_IDS_STR});")
            print(f"[{target_db}] Cascaded deletion complete.")

            # 3. Clean up orphaned users
            cur.execute(
                "DELETE FROM users WHERE id IN ("
                "  SELECT u.id FROM users u LEFT JOIN memberships m ON u.id = m.user_id WHERE m.id IS NULL"
                ");"
            )
            deleted_users_count = cur.rowcount
            print(f"[{target_db}] Purged {deleted_users_count} orphaned users with 0 memberships.")

        conn.commit()

    # 4. Run Seed & Test Account Creation using SQLAlchemy models
    print(f"\n[{target_db}] Seeding kept businesses and test accounts...")
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session
    from callwise.db.seed import seed_businesses
    from callwise.db.models import User, Membership
    from callwise.api.security import hash_password

    sync_engine = create_engine(db_url)
    with Session(sync_engine) as session:
        seed_businesses(session)
        session.commit()
    print(f"[{target_db}] Seeded Aarav Clinic and Luxe Glow data & vector chunks.")

    TEST_USERS = [
        {
            "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000001"),
            "email": "aarav.owner@test.com",
            "name": "Dr. Aarav Sharma",
            "password": "Password123!",
            "business_id": KEPT_IDS[0],
            "role": "owner",
        },
        {
            "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000002"),
            "email": "aarav.manager@test.com",
            "name": "Dr. Priya Nair",
            "password": "Password123!",
            "business_id": KEPT_IDS[0],
            "role": "manager",
        },
        {
            "id": uuid.UUID("aaaaaaaa-1111-0000-0000-000000000003"),
            "email": "aarav.staff@test.com",
            "name": "Neha Frontdesk",
            "password": "Password123!",
            "business_id": KEPT_IDS[0],
            "role": "staff",
        },
        {
            "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000001"),
            "email": "salon.owner@test.com",
            "name": "Chloe Glow",
            "password": "Password123!",
            "business_id": KEPT_IDS[1],
            "role": "owner",
        },
        {
            "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000002"),
            "email": "salon.manager@test.com",
            "name": "Mike Stylist",
            "password": "Password123!",
            "business_id": KEPT_IDS[1],
            "role": "manager",
        },
        {
            "id": uuid.UUID("bbbbbbbb-2222-0000-0000-000000000003"),
            "email": "salon.staff@test.com",
            "name": "Samantha Assistant",
            "password": "Password123!",
            "business_id": KEPT_IDS[1],
            "role": "staff",
        },
    ]

    with Session(sync_engine) as session:
        for u_data in TEST_USERS:
            user = session.scalar(select(User).where(User.email == u_data["email"]))
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
                session.flush()
            else:
                user.name = u_data["name"]
                user.password_hash = pwd_hash
                user.is_active = True
                session.flush()

            membership = session.scalar(
                select(Membership).where(
                    Membership.user_id == user.id,
                    Membership.business_id == u_data["business_id"],
                )
            )
            if not membership:
                membership = Membership(
                    user_id=user.id,
                    business_id=u_data["business_id"],
                    role=u_data["role"],
                )
                session.add(membership)
            else:
                membership.role = u_data["role"]
            session.flush()

        session.commit()
    print(f"[{target_db}] Seeded test accounts for Aarav Clinic and Luxe Glow.")
    sync_engine.dispose()

    # 5. Collect After Counts & Verification
    with psycopg.connect(db_url) as conn:
        print(f"\n[{target_db}] Collecting after-counts and verifying zero orphans...")
        after = get_table_counts(conn, target_db)

        rows = []
        rows.append(["businesses", before["businesses_total"], before["businesses_unkept"], after["businesses_total"], after["businesses_unkept"]])
        rows.append(["users", before["users_total"], before["users_orphaned"], after["users_total"], after["users_orphaned"]])

        any_orphans = False
        for tbl, col in FK_TABLES:
            b_tot = before[tbl]["total"]
            b_unk = before[tbl]["unkept"]
            a_tot = after[tbl]["total"]
            a_unk = after[tbl]["unkept"]
            if a_unk > 0:
                any_orphans = True
            rows.append([f"{tbl}.{col}", b_tot, b_unk, a_tot, a_unk])

        print("\n" + tabulate(
            rows,
            headers=["Table / Field", "Before Total", "Before Unkept", "After Total", "After Unkept (Orphans)"],
            tablefmt="grid"
        ))

        # Check businesses in db
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, business_type, timezone FROM businesses ORDER BY name;")
            biz_list = cur.fetchall()
            print(f"\n[{target_db}] Final Remaining Businesses ({len(biz_list)}):")
            for b in biz_list:
                print(f"  • {b[1]} ({b[0]}) - {b[2]} [{b[3]}]")

        if any_orphans:
            print(f"\n❌ ERROR: Detected non-zero orphan records in [{target_db}]!")
            sys.exit(1)
        elif len(biz_list) != 2:
            print(f"\n❌ ERROR: Expected exactly 2 businesses in [{target_db}], got {len(biz_list)}!")
            sys.exit(1)
        else:
            print(f"\n✅ SUCCESS: Exactly 2 businesses and ZERO orphans across all 24 foreign key tables in [{target_db}]!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reduce demo businesses to Indian clinic & Salon")
    parser.add_argument("--db-url", required=True, help="PostgreSQL connection string")
    parser.add_argument("--confirm", action="store_true", help="Explicit confirmation required to run on 'callwise'")
    args = parser.parse_args()
    run_reduction(args.db_url, confirm=args.confirm)
