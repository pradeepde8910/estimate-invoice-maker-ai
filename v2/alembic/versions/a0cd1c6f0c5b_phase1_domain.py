"""phase1_domain

Revision ID: a0cd1c6f0c5b
Revises: 1e43e15598d4
Create Date: 2026-08-17 15:23:28.400547

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0cd1c6f0c5b'
down_revision: Union[str, None] = '1e43e15598d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
