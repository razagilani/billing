"""dropping fb_utility_name column

Revision ID: 18a02dea5969
Revises: fc9faca7a7f
Create Date: 2014-08-12 14:52:35.828156

"""

# revision identifiers, used by Alembic.
revision = '18a02dea5969'
down_revision = '42f84150db03'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.drop_column('customer', 'fb_utility_name')
    op.drop_column('utilbill', 'utility')


def downgrade():
    op.add_column('customer', sa.Column('fb_utility_name',
                                        mysql.VARCHAR(length=255),
                                        nullable=False))
    op.add_column('utilbill', sa.Column('utility',
                                         mysql.VARCHAR(length=24),
                                         nullable=False))