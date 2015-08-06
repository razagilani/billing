"""reebill.utilbill_id_not_null

Revision ID: 1953b5abb480
Revises: 686dfe445fd
Create Date: 2015-07-28 16:11:13.289220

"""

# revision identifiers, used by Alembic.
revision = '1953b5abb480'
down_revision = '686dfe445fd'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('reebill', 'utilbill_id', nullable=False)


def downgrade():
    raise NotImplementedError
