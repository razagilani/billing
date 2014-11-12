"""Drop Old rate_class columns from UtilBill and Customer

Revision ID: 4bc721447593
Revises: 165d171d3a34
Create Date: 2014-10-24 17:44:31.450516

"""

# revision identifiers, used by Alembic.
revision = '4bc721447593'
down_revision = '3566e62e7af3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('customer', 'fb_rate_class')
    op.drop_column('utilbill', 'rate_class')


def downgrade():
    op.add_column('customer', sa.Column('fb_rate_class', sa.String(255), nullable=False))
    op.add_column('utilbill', sa.Column('rate_class', sa.String(255), nullable=False))
