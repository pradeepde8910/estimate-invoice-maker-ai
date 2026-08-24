"""Add Resource & Capability Costing Engine foundation tables

Revision ID: c4d8f1a9e6b2
Revises: 9b3e5c7a1d2f
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d8f1a9e6b2'
down_revision: Union[str, None] = '9b3e5c7a1d2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'capabilities',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(op.f('ix_capabilities_key'), 'capabilities', ['key'], unique=True)

    op.create_table(
        'technology_providers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(op.f('ix_technology_providers_key'), 'technology_providers', ['key'], unique=True)

    op.create_table(
        'technology_models',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('provider_id', sa.String(length=36), nullable=False),
        sa.Column('capability_id', sa.String(length=36), nullable=False),
        sa.Column('model_key', sa.String(length=100), nullable=False),
        sa.Column('model_name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['technology_providers.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'model_features',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('model_id', sa.String(length=36), nullable=False),
        sa.Column('feature_key', sa.String(length=100), nullable=False),
        sa.Column('feature_value', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['technology_models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'api_pricing_rules',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('model_id', sa.String(length=36), nullable=False),
        sa.Column('pricing_model', sa.String(length=30), nullable=False),
        sa.Column('unit_type', sa.String(length=50), nullable=True),
        sa.Column('price', sa.Numeric(precision=12, scale=4), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False),
        sa.Column('minimum_commitment', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tier_config', sa.Text(), nullable=True),
        sa.Column('pricing_source', sa.String(length=30), nullable=False),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('last_verified_on', sa.DateTime(), nullable=True),
        sa.Column('effective_from', sa.DateTime(), nullable=True),
        sa.Column('effective_to', sa.DateTime(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['model_id'], ['technology_models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'resource_requirements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=True),
        sa.Column('estimation_id', sa.String(length=255), nullable=True),
        sa.Column('requirement_id', sa.String(length=100), nullable=True),
        sa.Column('capability_id', sa.String(length=36), nullable=False),
        sa.Column('resolved_model_id', sa.String(length=36), nullable=True),
        sa.Column('vendor_constraint_provider_id', sa.String(length=36), nullable=True),
        sa.Column('vendor_constraint_type', sa.String(length=20), nullable=True),
        sa.Column('usage_metric', sa.String(length=100), nullable=True),
        sa.Column('usage_value', sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column('usage_period', sa.String(length=20), nullable=True),
        sa.Column('usage_source', sa.String(length=30), nullable=True),
        sa.Column('usage_confidence', sa.String(length=20), nullable=True),
        sa.Column('selection_reason', sa.Text(), nullable=True),
        sa.Column('monthly_cost', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['resolved_model_id'], ['technology_models.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['vendor_constraint_provider_id'], ['technology_providers.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('resource_requirements')
    op.drop_table('api_pricing_rules')
    op.drop_table('model_features')
    op.drop_table('technology_models')
    op.drop_index(op.f('ix_technology_providers_key'), table_name='technology_providers')
    op.drop_table('technology_providers')
    op.drop_index(op.f('ix_capabilities_key'), table_name='capabilities')
    op.drop_table('capabilities')
