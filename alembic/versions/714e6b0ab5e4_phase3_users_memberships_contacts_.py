"""phase3_users_memberships_contacts_followups

Revision ID: 714e6b0ab5e4
Revises: ad1c36f2a038
Create Date: 2026-11-07 01:48:38.680873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '714e6b0ab5e4'
down_revision: Union[str, Sequence[str], None] = 'ad1c36f2a038'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add users, memberships, sessions, invites, audit_log, jobs, contacts, follow_ups."""
    # 1. Users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # 2. Audit Log
    op.create_table(
        'audit_log',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=255), nullable=True),
        sa.Column('changes', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_log_business_id'), 'audit_log', ['business_id'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)
    op.create_index(op.f('ix_audit_log_user_id'), 'audit_log', ['user_id'], unique=False)

    # 3. Contacts
    op.create_table(
        'contacts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('do_not_contact', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contacts_business_email', 'contacts', ['business_id', 'email'], unique=False)
    op.create_index(op.f('ix_contacts_business_id'), 'contacts', ['business_id'], unique=False)
    op.create_index('ix_contacts_business_phone', 'contacts', ['business_id', 'phone'], unique=False)
    op.create_index(op.f('ix_contacts_email'), 'contacts', ['email'], unique=False)
    op.create_index(op.f('ix_contacts_phone'), 'contacts', ['phone'], unique=False)

    # 4. Invites
    op.create_table(
        'invites',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('invited_by_user_id', sa.UUID(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_invites_business_id'), 'invites', ['business_id'], unique=False)
    op.create_index(op.f('ix_invites_email'), 'invites', ['email'], unique=False)
    op.create_index(op.f('ix_invites_token_hash'), 'invites', ['token_hash'], unique=True)

    # 5. Jobs
    op.create_table(
        'jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('progress', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_jobs_business_id'), 'jobs', ['business_id'], unique=False)
    op.create_index(op.f('ix_jobs_created_at'), 'jobs', ['created_at'], unique=False)
    op.create_index(op.f('ix_jobs_status'), 'jobs', ['status'], unique=False)

    # 6. Memberships
    op.create_table(
        'memberships',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memberships_business_id'), 'memberships', ['business_id'], unique=False)
    op.create_index(op.f('ix_memberships_user_id'), 'memberships', ['user_id'], unique=False)
    op.create_index('uq_memberships_user_business', 'memberships', ['user_id', 'business_id'], unique=True)

    # 7. Password Resets
    op.create_table(
        'password_resets',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_resets_token_hash'), 'password_resets', ['token_hash'], unique=True)
    op.create_index(op.f('ix_password_resets_user_id'), 'password_resets', ['user_id'], unique=False)

    # 8. Sessions
    op.create_table(
        'sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('session_token_hash', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('current_business_id', sa.UUID(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ip_address', sa.String(length=100), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('last_active_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['current_business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sessions_expires_at'), 'sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_sessions_session_token_hash'), 'sessions', ['session_token_hash'], unique=True)
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)

    # 9. Follow-ups
    op.create_table(
        'follow_ups',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('contact_id', sa.UUID(), nullable=True),
        sa.Column('assigned_to_user_id', sa.UUID(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
        sa.Column('snoozed_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_follow_ups_assigned_to_user_id'), 'follow_ups', ['assigned_to_user_id'], unique=False)
    op.create_index(op.f('ix_follow_ups_business_id'), 'follow_ups', ['business_id'], unique=False)
    op.create_index(op.f('ix_follow_ups_contact_id'), 'follow_ups', ['contact_id'], unique=False)
    op.create_index(op.f('ix_follow_ups_created_at'), 'follow_ups', ['created_at'], unique=False)
    op.create_index(op.f('ix_follow_ups_status'), 'follow_ups', ['status'], unique=False)

    # 10. Alter existing tables
    op.add_column('businesses', sa.Column('retention_days', sa.Integer(), nullable=True, server_default=sa.text('90')))
    op.add_column('businesses', sa.Column('website_url', sa.String(length=500), nullable=True))

    op.add_column(
        'knowledge_misses',
        sa.Column('status', sa.String(length=50), nullable=False, server_default='unresolved')
    )
    op.add_column('knowledge_misses', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('knowledge_misses', sa.Column('resolved_answer', sa.Text(), nullable=True))
    op.create_index(op.f('ix_knowledge_misses_status'), 'knowledge_misses', ['status'], unique=False)

    op.add_column('appointments', sa.Column('contact_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_appointments_contact_id'), 'appointments', ['contact_id'], unique=False)
    op.create_foreign_key(
        'fk_appointments_contact_id_contacts',
        'appointments',
        'contacts',
        ['contact_id'],
        ['id'],
        ondelete='SET NULL'
    )

    op.add_column('calls', sa.Column('contact_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_calls_contact_id'), 'calls', ['contact_id'], unique=False)
    op.create_foreign_key(
        'fk_calls_contact_id_contacts',
        'calls',
        'contacts',
        ['contact_id'],
        ['id'],
        ondelete='SET NULL'
    )

    op.add_column('messages', sa.Column('contact_id', sa.UUID(), nullable=True))
    op.create_index(op.f('ix_messages_contact_id'), 'messages', ['contact_id'], unique=False)
    op.create_foreign_key(
        'fk_messages_contact_id_contacts',
        'messages',
        'contacts',
        ['contact_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # 11. Backfill contacts from existing appointments, messages, and calls
    op.execute(
        """
        INSERT INTO contacts (id, business_id, name, phone, email, notes, do_not_contact, created_at, updated_at)
        SELECT DISTINCT ON (business_id, customer_phone)
            gen_random_uuid(),
            business_id,
            customer_name,
            customer_phone,
            NULLIF(LOWER(TRIM(customer_email)), ''),
            'Auto-created from appointment history',
            false,
            NOW(),
            NOW()
        FROM appointments
        WHERE customer_phone IS NOT NULL AND customer_phone != ''
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE appointments a
        SET contact_id = c.id
        FROM contacts c
        WHERE a.business_id = c.business_id AND a.customer_phone = c.phone AND a.contact_id IS NULL;
        """
    )
    op.execute(
        """
        INSERT INTO contacts (id, business_id, name, phone, email, notes, do_not_contact, created_at, updated_at)
        SELECT DISTINCT ON (business_id, callback_number)
            gen_random_uuid(),
            business_id,
            caller_name,
            callback_number,
            NULL,
            'Auto-created from callback message',
            false,
            NOW(),
            NOW()
        FROM messages
        WHERE callback_number IS NOT NULL AND callback_number != ''
          AND NOT EXISTS (
              SELECT 1 FROM contacts c WHERE c.business_id = messages.business_id AND c.phone = messages.callback_number
          )
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE messages m
        SET contact_id = c.id
        FROM contacts c
        WHERE m.business_id = c.business_id AND m.callback_number = c.phone AND m.contact_id IS NULL;
        """
    )
    op.execute(
        """
        INSERT INTO contacts (id, business_id, name, phone, email, notes, do_not_contact, created_at, updated_at)
        SELECT DISTINCT ON (business_id, caller_number)
            gen_random_uuid(),
            business_id,
            NULL,
            caller_number,
            NULL,
            'Auto-created from incoming call',
            false,
            NOW(),
            NOW()
        FROM calls
        WHERE caller_number IS NOT NULL AND caller_number NOT IN ('', 'unknown', 'anonymous', 'console')
          AND NOT EXISTS (
              SELECT 1 FROM contacts c WHERE c.business_id = calls.business_id AND c.phone = calls.caller_number
          )
        ON CONFLICT DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE calls ca
        SET contact_id = c.id
        FROM contacts c
        WHERE ca.business_id = c.business_id AND ca.caller_number = c.phone AND ca.contact_id IS NULL;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_messages_contact_id_contacts', 'messages', type_='foreignkey')
    op.drop_index(op.f('ix_messages_contact_id'), table_name='messages')
    op.drop_column('messages', 'contact_id')

    op.drop_constraint('fk_calls_contact_id_contacts', 'calls', type_='foreignkey')
    op.drop_index(op.f('ix_calls_contact_id'), table_name='calls')
    op.drop_column('calls', 'contact_id')

    op.drop_constraint('fk_appointments_contact_id_contacts', 'appointments', type_='foreignkey')
    op.drop_index(op.f('ix_appointments_contact_id'), table_name='appointments')
    op.drop_column('appointments', 'contact_id')

    op.drop_index(op.f('ix_knowledge_misses_status'), table_name='knowledge_misses')
    op.drop_column('knowledge_misses', 'resolved_answer')
    op.drop_column('knowledge_misses', 'resolved_at')
    op.drop_column('knowledge_misses', 'status')

    op.drop_column('businesses', 'website_url')
    op.drop_column('businesses', 'retention_days')

    op.drop_index(op.f('ix_follow_ups_status'), table_name='follow_ups')
    op.drop_index(op.f('ix_follow_ups_created_at'), table_name='follow_ups')
    op.drop_index(op.f('ix_follow_ups_contact_id'), table_name='follow_ups')
    op.drop_index(op.f('ix_follow_ups_business_id'), table_name='follow_ups')
    op.drop_index(op.f('ix_follow_ups_assigned_to_user_id'), table_name='follow_ups')
    op.drop_table('follow_ups')

    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_session_token_hash'), table_name='sessions')
    op.drop_index(op.f('ix_sessions_expires_at'), table_name='sessions')
    op.drop_table('sessions')

    op.drop_index(op.f('ix_password_resets_user_id'), table_name='password_resets')
    op.drop_index(op.f('ix_password_resets_token_hash'), table_name='password_resets')
    op.drop_table('password_resets')

    op.drop_index('uq_memberships_user_business', table_name='memberships')
    op.drop_index(op.f('ix_memberships_user_id'), table_name='memberships')
    op.drop_index(op.f('ix_memberships_business_id'), table_name='memberships')
    op.drop_table('memberships')

    op.drop_index(op.f('ix_jobs_status'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_created_at'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_business_id'), table_name='jobs')
    op.drop_table('jobs')

    op.drop_index(op.f('ix_invites_token_hash'), table_name='invites')
    op.drop_index(op.f('ix_invites_email'), table_name='invites')
    op.drop_index(op.f('ix_invites_business_id'), table_name='invites')
    op.drop_table('invites')

    op.drop_index(op.f('ix_contacts_phone'), table_name='contacts')
    op.drop_index(op.f('ix_contacts_email'), table_name='contacts')
    op.drop_index('ix_contacts_business_phone', table_name='contacts')
    op.drop_index(op.f('ix_contacts_business_id'), table_name='contacts')
    op.drop_index('ix_contacts_business_email', table_name='contacts')
    op.drop_table('contacts')

    op.drop_index(op.f('ix_audit_log_user_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_business_id'), table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
