"""added reebill_id column to payment table

Revision ID: 6446c51511c
Revises: 2e47f4f18a8b
Create Date: 2014-09-04 13:45:12.662964

"""

# revision identifiers, used by Alembic.
revision = '6446c51511c'
down_revision = '2e47f4f18a8b'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('payment',
    sa.Column('reebill_id', sa.INTEGER, sa.ForeignKey('reebill.id'))
)


def downgrade():
    op.drop_column('payment', 'reebill_id')
