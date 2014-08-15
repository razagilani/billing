"""adding fb_utility_id column to customer

Revision ID: fc9faca7a7f
Revises: 1a174da18305
Create Date: 2014-08-12 14:44:20.720168

"""

# revision identifiers, used by Alembic.
revision = 'fc9faca7a7f'
down_revision = '1a174da18305'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column('customer', sa.Column('fb_utility_id', sa.Integer(), nullable=True))
    op.add_column('utilbill', sa.Column('utility_id', sa.Integer(), nullable=True))
    op.add_column('utilbill', sa.Column('sha256_hexdigest', sa.String(length=64), nullable=True))

def downgrade():
    op.drop_column('customer', 'fb_utility_id')
    op.drop_column('utilbill', 'utility_id')
    op.drop_column('utilbill', 'sha256_hexdigest')
