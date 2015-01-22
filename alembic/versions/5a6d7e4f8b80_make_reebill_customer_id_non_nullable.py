"""make reebill_customer_id non nullable

Revision ID: 5a6d7e4f8b80
Revises: 28552fdf9f48
Create Date: 2014-12-23 14:49:38.251881

"""

# revision identifiers, used by Alembic.
revision = '5a6d7e4f8b80'
down_revision = '28552fdf9f48'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('reebill', 'reebill_customer_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
     op.alter_column('reebill', 'reebill_customer_id', existing_type=sa.Integer(), nullable=True)
