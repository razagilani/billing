"""schema 26

Revision ID: 23a21392b372
Revises: 52a7069819cb
Create Date: 2015-03-17 16:27:49.168003

"""

# revision identifiers, used by Alembic.
revision = '23a21392b372'
down_revision = '52a7069819cb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('reebill_customer',
                  sa.Column('tag', sa.String(1000), nullable=False))

def downgrade():
    op.drop_column('reebill_customer', 'tag')

