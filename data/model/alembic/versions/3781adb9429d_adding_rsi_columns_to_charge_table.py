"""adding rsi columns to charge table

Revision ID: 3781adb9429d
Revises: 2a89489227e
Create Date: 2014-06-12 15:22:21.298709

"""

# revision identifiers, used by Alembic.
revision = '3781adb9429d'
down_revision = '3f16438c6c50'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.add_column(u'charge', sa.Column('has_charge', sa.Boolean(), nullable=False))
    op.add_column(u'charge', sa.Column('quantity_formula', sa.String(length=1000), nullable=False))
    op.add_column(u'charge', sa.Column('rate_formula', sa.String(length=1000), nullable=False))
    op.add_column(u'charge', sa.Column('roundrule', sa.String(length=1000), nullable=True))
    op.add_column(u'charge', sa.Column('shared', sa.Boolean(), nullable=False))

def downgrade():
    op.drop_column(u'charge', 'shared')
    op.drop_column(u'charge', 'roundrule')
    op.drop_column(u'charge', 'rate_formula')
    op.drop_column(u'charge', 'quantity_formula')
    op.drop_column(u'charge', 'has_charge')
