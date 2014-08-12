"""dropping fb_utility_name column

Revision ID: 18a02dea5969
Revises: fc9faca7a7f
Create Date: 2014-08-12 14:52:35.828156

"""

# revision identifiers, used by Alembic.
revision = '18a02dea5969'
down_revision = 'fc9faca7a7f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.drop_column('customer', 'fb_utility_name')


def downgrade():
    op.add_column('customer', sa.Column('fb_utility_name',
                                        mysql.VARCHAR(length=255),
                                        nullable=False))
