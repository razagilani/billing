"""dropping template id column

Revision ID: 2e47f4f18a8b
Revises: 39efff02706c
Create Date: 2014-08-11 18:28:39.169590

"""

# revision identifiers, used by Alembic.
revision = '2e47f4f18a8b'
down_revision = '32bbb4189c1'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.drop_column(u'customer', 'utilbill_template_id')
    op.drop_column('charge', 'rate_formula')


def downgrade():
    op.add_column(u'customer', sa.Column('utilbill_template_id',
                                    mysql.VARCHAR(length=24), nullable=False))
    op.add_column('charge', sa.Column('rate_formula',
                                mysql.VARCHAR(length=1000), nullable=False))

