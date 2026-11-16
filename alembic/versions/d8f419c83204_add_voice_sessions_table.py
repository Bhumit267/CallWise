"""add voice_sessions table for secure per-call web voice routing

Revision ID: d8f419c83204
Revises: c5e829fa1102
Create Date: 2026-11-16 09:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8f419c83204'
down_revision: Union[str, None] = 'c5e829fa1102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voice_sessions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('business_id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('caller_identity', sa.String(length=100), nullable=False),
        sa.Column('room_name', sa.String(length=100), nullable=False),
        sa.Column('call_id', sa.UUID(), nullable=False),
        sa.Column('is_used', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_voice_sessions_business_id'), 'voice_sessions', ['business_id'], unique=False)
    op.create_index(op.f('ix_voice_sessions_expires_at'), 'voice_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_voice_sessions_room_name'), 'voice_sessions', ['room_name'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_voice_sessions_room_name'), table_name='voice_sessions')
    op.drop_index(op.f('ix_voice_sessions_expires_at'), table_name='voice_sessions')
    op.drop_index(op.f('ix_voice_sessions_business_id'), table_name='voice_sessions')
    op.drop_table('voice_sessions')
