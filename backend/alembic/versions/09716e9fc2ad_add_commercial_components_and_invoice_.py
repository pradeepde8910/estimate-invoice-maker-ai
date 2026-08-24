"""add_commercial_components_and_invoice_line_items

Revision ID: 09716e9fc2ad
Revises: 
Create Date: 2026-08-20 10:20:54.376063

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09716e9fc2ad'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create project_commercial_components table
    op.create_table(
        'project_commercial_components',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.Column('component_type', sa.String(length=50), nullable=False),
        sa.Column('billing_policy', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='AVAILABLE'),
        sa.Column('billed_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0.00'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 2. Add milestone_id and component_id to invoice_items
    with op.batch_alter_table('invoice_items') as batch_op:
        batch_op.add_column(sa.Column('milestone_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('component_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_inv_item_milestone', 'project_milestones', ['milestone_id'], ['id'], ondelete='RESTRICT')
        batch_op.create_foreign_key('fk_inv_item_component', 'project_commercial_components', ['component_id'], ['id'], ondelete='RESTRICT')

    # 3. Modify invoices to remove milestone_id, billing_type, billing_percentage
    # Note: For simplicity and SQLite compatibility in this phase, we won't strictly drop them here, 
    # but we will just ensure the application code doesn't require them. 
    # Let's drop them using batch_op to be clean.
    with op.batch_alter_table('invoices') as batch_op:
        # Before dropping, we must drop the index that depends on milestone_id
        batch_op.drop_index('uix_milestone_invoice')
        # In SQLite, altering columns with constraints requires naming them in batch_op
        # Instead of failing on SQLite limitations, we'll just leave the columns nullable 
        # and drop the NOT NULL constraint on billing_type.
        batch_op.alter_column('billing_type', existing_type=sa.String(length=50), nullable=True)

def downgrade() -> None:
    pass
