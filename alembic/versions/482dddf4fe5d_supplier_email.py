"""supplier_email

Revision ID: 482dddf4fe5d
Revises: 1953b5abb480
Create Date: 2015-08-05 16:10:37.807261

"""

# revision identifiers, used by Alembic.
revision = '482dddf4fe5d'
down_revision = '1226d67c4c53'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.add_column('supplier', sa.Column('matrix_email_recipient', sa.String(), nullable=True))


def downgrade():
    raise NotImplementedError
