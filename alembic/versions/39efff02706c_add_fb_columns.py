"""add fb columns

Revision ID: 39efff02706c
Revises: 3781adb9429d
Create Date: 2014-07-30 19:24:49.441497

"""

# revision identifiers, used by Alembic.
revision = '39efff02706c'
down_revision = '3781adb9429d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # note this is nullable for brokerage customers that do not have a service type
    op.add_column('customer', sa.Column('service', sa.Enum('thermal', 'pv')))

    op.add_column(u'customer', sa.Column('fb_billing_address_id', sa.Integer(), nullable=False))
    op.add_column(u'customer', sa.Column('fb_rate_class', sa.String(length=255), nullable=False))
    op.add_column(u'customer', sa.Column('fb_service_address_id', sa.Integer(), nullable=False))
    op.add_column(u'customer', sa.Column('fb_utility_name', sa.String(length=255), nullable=False))


def downgrade():
    op.drop_column(u'customer', 'fb_utility_name')
    op.drop_column(u'customer', 'fb_service_address_id')
    op.drop_column(u'customer', 'fb_rate_class')
    op.drop_column(u'customer', 'fb_billing_address_id')
    op.drop_column('customer', 'service')
