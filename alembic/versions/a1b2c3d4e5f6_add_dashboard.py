"""add dashboard table

Revision ID: a1b2c3d4e5f6
Revises: dfeac34fb4f1
Create Date: 2026-07-03 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'dfeac34fb4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dashboards',
    sa.Column('id', sa.Text(), nullable=False),
    sa.Column('session_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('widgets', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('dashboards')
