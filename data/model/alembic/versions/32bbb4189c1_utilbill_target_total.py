"""utilbill_target_total

Revision ID: 32bbb4189c1
Revises: 39efff02706c
Create Date: 2014-09-15 13:40:14.220181

"""

# revision identifiers, used by Alembic.
revision = '32bbb4189c1'
down_revision = '39efff02706c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('utilbill', 'total_charges', existing_type=sa.Float, name='target_total')

def downgrade():
    op.alter_column('utilbill', 'target_total', existing_type=sa.Float, name='total_charges')
