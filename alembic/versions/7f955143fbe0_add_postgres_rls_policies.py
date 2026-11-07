"""add_postgres_rls_policies

Revision ID: 7f955143fbe0
Revises: 714e6b0ab5e4
Create Date: 2026-11-07 11:25:52.315110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f955143fbe0'
down_revision: Union[str, Sequence[str], None] = '714e6b0ab5e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TENANT_TABLES = [
    "documents",
    "chunks",
    "calls",
    "call_turns",
    "messages",
    "knowledge_misses",
    "services",
    "appointments",
    "transfers",
    "notifications",
    "reminders",
    "contacts",
    "follow_ups",
    "jobs",
    "audit_log",
    "invites",
    "memberships",
]


def upgrade() -> None:
    """Enable Row Level Security and configure tenant isolation policies across all tenant tables."""
    # 0. Create non-superuser application role that cannot bypass RLS
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'callwise_app') THEN
                CREATE ROLE callwise_app WITH LOGIN PASSWORD 'callwise_app' NOSUPERUSER NOBYPASSRLS;
            END IF;
            GRANT ALL PRIVILEGES ON DATABASE callwise TO callwise_app;
            GRANT ALL ON SCHEMA public TO callwise_app;
            GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO callwise_app;
            GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO callwise_app;
            ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO callwise_app;
        END
        $$;
        """
    )

    for table in TENANT_TABLES:
        # 1. Enable RLS
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        # 2. Force RLS (applies to table owners and standard application roles alike)
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        # 3. Create tenant isolation policy based on per-transaction session setting 'app.current_business_id'
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {table}
            FOR ALL
            USING (
                current_setting('app.current_business_id', true) IS NULL
                OR current_setting('app.current_business_id', true) = ''
                OR business_id::text = current_setting('app.current_business_id', true)
            )
            WITH CHECK (
                current_setting('app.current_business_id', true) IS NULL
                OR current_setting('app.current_business_id', true) = ''
                OR business_id::text = current_setting('app.current_business_id', true)
            );
            """
        )


def downgrade() -> None:
    """Disable Row Level Security and remove tenant isolation policies."""
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
