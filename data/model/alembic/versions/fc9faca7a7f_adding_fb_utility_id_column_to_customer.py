"""adding fb_utility_id column to customer

Revision ID: fc9faca7a7f
Revises: 1a174da18305
Create Date: 2014-08-12 14:44:20.720168

"""

# revision identifiers, used by Alembic.
revision = 'fc9faca7a7f'
down_revision = '1a174da18305'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.add_column('customer', sa.Column('fb_utility_id', sa.Integer(), nullable=True))
    op.add_column('utilbill', sa.Column('utility_id', sa.Integer(), nullable=True))
    op.add_column('utilbill', sa.Column('sha256_hexdigest', sa.String(length=64), nullable=True))
    op.add_column('company', sa.Column('guid', sa.String(length=36), nullable=False))
    op.create_table('supplier',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('company_id', sa.Integer(), sa.ForeignKey('company.id')),
    sa.PrimaryKeyConstraint('id'))
    op.add_column('utilbill',
    sa.Column('supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id')))
    op.add_column('customer',
    sa.Column('fb_supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id'))
)

def downgrade():
    op.drop_column('customer', 'fb_utility_id')
    op.drop_column('utilbill', 'utility_id')
    op.drop_column('utilbill', 'sha256_hexdigest')
    op.drop_column('company', 'guid')
    op.drop_table('supplier')
    op.drop_column('utilbill', 'supplier_id')
    op.drop_column('customer', 'fb_supplier_id')
