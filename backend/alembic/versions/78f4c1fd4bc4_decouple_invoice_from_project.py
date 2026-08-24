"""Decouple invoice from project

Revision ID: 78f4c1fd4bc4
Revises: 22a49390979b
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78f4c1fd4bc4'
down_revision: Union[str, None] = '22a49390979b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('invoice_type', sa.String(length=20), nullable=False, server_default='PROJECT'))
        batch_op.alter_column('project_id', existing_type=sa.String(length=36), nullable=True)
        batch_op.create_check_constraint('chk_invoice_type', "invoice_type in ('PROJECT', 'STANDALONE')")


def downgrade() -> None:
    with op.batch_alter_table('invoices', schema=None) as batch_op:
        batch_op.drop_constraint('chk_invoice_type', type_='check')
        batch_op.alter_column('project_id', existing_type=sa.String(length=36), nullable=False)
        batch_op.drop_column('invoice_type')
