"""add due_date to utilbill

Revision ID: 42f84150db03
Revises: 28552fdf9f48
Create Date: 2014-12-10 16:48:57.450662

"""

# revision identifiers, used by Alembic.
revision = '42f84150db03'
down_revision = '507c0437a7f8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('utilbill', sa.Column('due_date', sa.Date()))



def downgrade():
     op.drop_column('utilbill', 'due_date')

