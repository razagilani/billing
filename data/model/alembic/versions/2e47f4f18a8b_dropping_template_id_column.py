"""dropping template id column

Revision ID: 2e47f4f18a8b
Revises: 39efff02706c
Create Date: 2014-08-11 18:28:39.169590

"""

# revision identifiers, used by Alembic.
revision = '2e47f4f18a8b'
down_revision = '39efff02706c'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column(u'customer', 'utilbill_template_id')


def downgrade():
    op.add_column(u'customer', sa.Column('utilbill_template_id',
                                         mysql.VARCHAR(length=24), nullable=False))
