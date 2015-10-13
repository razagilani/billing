"""Added processed column to reebill table

Revision ID: 4f2f8e2f7cd
Revises: 55e7e5ebdd29
Create Date: 2014-05-29 11:02:46.115863

"""

# revision identifiers, used by Alembic.
revision = '4f2f8e2f7cd'
down_revision = '55e7e5ebdd29'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.add_column(u'reebill', sa.Column('processed', sa.Boolean(), nullable=True))
    op.add_column(u'utilbill', sa.Column('billing_address_id', sa.Integer(), nullable=False))
    op.add_column(u'utilbill', sa.Column('service_address_id', sa.Integer(), nullable=False))


def downgrade():
    op.drop_column(u'reebill', 'processed')
    op.drop_column(u'utilbill', 'service_address_id')
    op.drop_column(u'utilbill', 'billing_address_id')
