"""add intent urgency sentiment tags to calls

Revision ID: c5e829fa1102
Revises: b3d9c18f2a01
Create Date: 2026-11-14 03:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5e829fa1102'
down_revision: Union[str, None] = 'b3d9c18f2a01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('calls', sa.Column('intent', sa.String(length=50), nullable=True))
    op.add_column('calls', sa.Column('urgency', sa.String(length=20), server_default='normal', nullable=True))
    op.add_column('calls', sa.Column('sentiment', sa.String(length=20), server_default='neutral', nullable=True))
    op.add_column('calls', sa.Column('tags', sa.JSON(), server_default='[]', nullable=True))
    op.add_column('calls', sa.Column('structured_notes', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('calls', 'structured_notes')
    op.drop_column('calls', 'tags')
    op.drop_column('calls', 'sentiment')
    op.drop_column('calls', 'urgency')
    op.drop_column('calls', 'intent')

