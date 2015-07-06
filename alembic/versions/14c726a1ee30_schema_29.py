"""schema 29

Revision ID: 14c726a1ee30
Revises: 30597f9f53b9
Create Date: 2015-06-30 14:33:19.453671

"""

# revision identifiers, used by Alembic.
revision = '14c726a1ee30'
down_revision = '41bb5135c2b6'

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
    op.rename_table('quote', 'Rate_Matrix')

    op.add_column('supplier', sa.Column('matrix_file_name', sa.String))
    op.create_unique_constraint('uq_supplier_matrix_file_name', 'supplier',
                                ['matrix_file_name'])

    op.create_table('Company',
                    sa.Column('Company_ID', sa.Integer, primary_key=True),
                    sa.Column('Company', sa.String, unique=True))

    op.create_table('Company_PG_Supplier',
                    sa.Column('Company_ID', sa.Integer, primary_key=True),
                    sa.Column('Company', sa.String, unique=True))

    op.create_table('Rate_Class_View',
                    sa.Column('Rate_Class_ID', sa.Integer, primary_key=True))
    op.create_table('Rate_Class_Alias',
                    sa.Column('Rate_Class_Alias_ID', sa.Integer,
                              primary_key=True),
                    sa.Column('Rate_Class_ID', sa.Integer,
                              sa.ForeignKey('Rate_Class_View.Rate_Class_ID')),
                    sa.Column('Rate_Class_Alias', sa.String, nullable=False))

def downgrade():
    raise NotImplementedError
