"""matrix_file_name

Revision ID: 127c3e14d9d4
Revises: 482dddf4fe5d
Create Date: 2015-10-23 18:33:38.140637

"""

# revision identifiers, used by Alembic.
revision = '127c3e14d9d4'
down_revision = '482dddf4fe5d'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.drop_column('supplier', 'matrix_file_name')
    #op.drop_constraint(u'uq_supplier_matrix_file_name', 'supplier')
    #op.drop_index('uq_supplier_matrix_file_name', table_name='supplier')


def downgrade():
    raise NotImplementedError
