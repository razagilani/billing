"""matrix_format

Revision ID: 4f589e8d4cab
Revises: 127c3e14d9d4
Create Date: 2015-12-03 17:24:26.508129

"""

# revision identifiers, used by Alembic.
revision = '4f589e8d4cab'
down_revision = '127c3e14d9d4'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table(
        'matrix_format',
        sa.Column('matrix_format_id', sa.Integer(), nullable=False),
        sa.Column('supplier_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('matrix_attachment_name', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id'], ),
        sa.PrimaryKeyConstraint('matrix_format_id')
    )


def downgrade():
    raise NotImplementedError
