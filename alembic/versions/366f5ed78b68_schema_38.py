"""schema_38

Revision ID: 366f5ed78b68
Revises: 2d5527ff438a
Create Date: 2015-12-09 12:11:52.406195

"""

# revision identifiers, used by Alembic.
revision = '366f5ed78b68'
down_revision = '2d5527ff438a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # should have been in version 37
    op.drop_column('supplier', 'matrix_attachment_name')

    op.add_column('Rate_Matrix', sa.Column('file_reference', sa.String))

def downgrade():
    raise NotImplementedError
