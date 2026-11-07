"""phase4_phone_usage_limits_widget_blocklist

Revision ID: b3d9c18f2a01
Revises: 7f955143fbe0
Create Date: 2026-11-07 14:35:00.000000

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3d9c18f2a01'
down_revision: Union[str, Sequence[str], None] = '7f955143fbe0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PHASE4_TENANT_TABLES = [
    "phone_numbers",
    "usage_records",
    "usage_limits",
    "widget_settings",
    "blocklist",
]


def upgrade() -> None:
    # 1. phone_numbers table
    op.create_table(
        "phone_numbers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("e164_number", sa.String(50), nullable=False, unique=True, index=True),
        sa.Column("provider", sa.String(50), nullable=False, server_default="livekit"),
        sa.Column("label", sa.String(100), nullable=False, server_default="Main Inbound"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 2. usage_records table (tracks cost, minutes, tokens, stt/tts metrics per call/chat)
    op.create_table(
        "usage_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calls.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("session_type", sa.String(50), nullable=False, server_default="phone"),  # phone, widget, test_console
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stt_seconds", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("tts_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_provider", sa.String(50), nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("tts_provider", sa.String(50), nullable=True),
        sa.Column("stt_provider", sa.String(50), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False, index=True),
    )

    # 3. usage_limits table (configured by platform admin, read-only to owners)
    op.create_table(
        "usage_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("voice_minutes_per_month", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("chat_messages_per_month", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("max_concurrent_calls", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("max_call_duration_seconds", sa.Integer(), nullable=False, server_default="600"),  # 10 min
        sa.Column("llm_tokens_per_month", sa.Integer(), nullable=False, server_default="500000"),
        sa.Column("hard_limit_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 4. widget_settings table (public key, allowed origins, greeting, styling)
    op.create_table(
        "widget_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column("public_key", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allowed_origins", sa.Text(), nullable=False, server_default="*"),  # comma-separated domains or *
        sa.Column("primary_color", sa.String(30), nullable=False, server_default="#2563EB"),
        sa.Column("greeting_message", sa.Text(), nullable=False, server_default="Hi! How can we help you today?"),
        sa.Column("ask_lead_capture", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("require_lead_name", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_booking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rate_limit_rpm", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_turns_per_session", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # 5. blocklist table (abuse protection: phone or IP block)
    op.create_table(
        "blocklist",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("identifier_type", sa.String(30), nullable=False),  # "phone", "ip"
        sa.Column("identifier_value", sa.String(100), nullable=False),  # e.g. "+15551234567" or "192.168.1.1"
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),  # null = permanent
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_blocklist_business_identifier",
        "blocklist",
        ["business_id", "identifier_type", "identifier_value"],
    )

    # 6. Enable RLS and tenant isolation policies for all new Phase 4 tables
    for table in PHASE4_TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
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
        # Grant access to callwise_app role
        op.execute(f"GRANT ALL PRIVILEGES ON TABLE {table} TO callwise_app;")


def downgrade() -> None:
    for table in reversed(PHASE4_TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")
        op.drop_table(table)

