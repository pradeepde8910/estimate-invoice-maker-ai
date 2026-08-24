"""Add payment_sequences table for voucher numbering

Revision ID: 9b3e5c7a1d2f
Revises: 7a2f9c1d4e3b
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b3e5c7a1d2f'
down_revision: Union[str, None] = '7a2f9c1d4e3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'payment_sequences',
        sa.Column('financial_year', sa.String(length=20), nullable=False),
        sa.Column('next_value', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('financial_year'),
    )


def downgrade() -> None:
    op.drop_table('payment_sequences')
