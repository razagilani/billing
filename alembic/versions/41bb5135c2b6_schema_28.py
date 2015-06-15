"""schema_28

Revision ID: 41bb5135c2b6
Revises: 58383ed620d3
Create Date: 2015-06-12 18:05:15.319226

"""

# revision identifiers, used by Alembic.
revision = '41bb5135c2b6'
down_revision = '58383ed620d3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('matrix_quote')
    op.add_column('quote', sa.Column('purchase_of_receivables', sa.Boolean,
                                     nullable=False))
    op.add_column('quote', sa.Column('min_volume', sa.Float))
    op.add_column('quote', sa.Column('limit_volume', sa.Float))
    op.rename_table('quote', 'rate')


def downgrade():
    raise NotImplementedError
