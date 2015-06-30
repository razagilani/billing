"""schema_28

Revision ID: 41bb5135c2b6
Revises: 58383ed620d3
Create Date: 2015-06-12 18:05:15.319226

"""

# revision identifiers, used by Alembic.
revision = '41bb5135c2b6'
down_revision = '58383ed620d3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('matrix_quote')
    op.add_column('quote', sa.Column('purchase_of_receivables', sa.Boolean,
                                     nullable=False))
    op.add_column('quote', sa.Column('min_volume', sa.Float))
    op.add_column('quote', sa.Column('limit_volume', sa.Float))
    op.add_column('quote', sa.Column('rate_class_alias', sa.String))
    op.alter_column('quote', 'supplier_id', nullable=True)
    op.rename_table('quote', 'rate')

    op.add_column('supplier', sa.Column('matrix_file_name', sa.String))
    op.create_unique_constraint('uq_supplier_matrix_file_name', 'supplier',
                                ['matrix_file_name'])

    op.create_table('Company',
                    sa.Column('Company_ID', sa.Integer, primary_key=True),
                    sa.Column('Company', sa.String, unique=True))

    op.create_table('Company_PG_Supplier',
                    sa.Column('Company_ID', sa.Integer, primary_key=True),
                    sa.Column('Company', sa.String, unique=True))


def downgrade():
    raise NotImplementedError
