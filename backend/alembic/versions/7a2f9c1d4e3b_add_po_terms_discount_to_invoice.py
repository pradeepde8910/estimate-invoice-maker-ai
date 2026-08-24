"""Add po_number, payment_terms, discount_amount to Invoice

Revision ID: 7a2f9c1d4e3b
Revises: 540e5adda193
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a2f9c1d4e3b'
down_revision: Union[str, None] = '540e5adda193'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('po_number', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('payment_terms', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('discount_amount', sa.Numeric(12, 2), nullable=False, server_default='0.00'))


def downgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_column('discount_amount')
        batch_op.drop_column('payment_terms')
        batch_op.drop_column('po_number')
