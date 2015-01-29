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
    op.add_column('utilbill', sa.Column('sha256_hexdigest', sa.String(
        length=64), nullable=False))
    op.alter_column('utilbill', 'period_end',
           existing_type=sa.DATE(),
           nullable=True)
    op.alter_column('utilbill', 'period_start',
           existing_type=sa.DATE(),
           nullable=True)

    op.create_table('supplier',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=255), nullable=True),
                    sa.Column('address_id', sa.Integer(), nullable=True),
                    sa.ForeignKeyConstraint(['address_id'], ['address.id'], ),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('name'),
    )
    op.add_column('utilbill',
            sa.Column('supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id'), nullable=True))
    op.add_column('customer',
            sa.Column('fb_supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id')))

    op.add_column('utilbill', sa.Column('date_scraped', sa.DateTime,
                                        nullable=True))
    op.create_table('rate_class',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=255), nullable=True),
                    sa.Column('utility_id', sa.Integer(),
                              sa.ForeignKey('utility.id')),
                    sa.PrimaryKeyConstraint('id'),
                    sa.UniqueConstraint('utility_id', 'name'),
    )
    op.add_column('customer', sa.Column('fb_rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id')))
    op.add_column('utilbill', sa.Column('rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id'), nullable=True))

    # tables for foreign keys to Altitude (many-to-1 with utility and supplier)
    # TODO: "company" will have to be replaced by utility
    op.create_table('altitude_utility',
                    sa.Column('utility_id', sa.Integer(),
                              sa.ForeignKey('utility.id'), nullable=False),
                    sa.Column('guid', sa.String(length=36), nullable=False),
                    sa.PrimaryKeyConstraint('utility_id', 'guid'))
    op.create_table('altitude_supplier',
                    sa.Column('supplier_id', sa.Integer(),
                              sa.ForeignKey('supplier.id'), nullable=False),
                    sa.Column('guid', sa.String(length=36), nullable=False),
                    sa.PrimaryKeyConstraint('supplier_id', 'guid'))
def downgrade():
    op.drop_column('customer', 'fb_utility_id')
    op.drop_column('utilbill', 'utility_id')
    op.drop_column('utilbill', 'sha256_hexdigest')
    op.alter_column('utilbill', 'period_end',
           existing_type=sa.DATE(),
           nullable=False)
    op.drop_table('supplier')
    op.drop_column('utilbill', 'supplier_id')
    op.drop_column('customer', 'fb_supplier_id')
    op.alter_column('utilbill', 'period_start',
           existing_type=sa.DATE(),
           nullable=False)
    op.drop_table('rate_class')
    op.drop_column('customer', 'fb_rate_class_id')
    op.drop_column('utilbill', 'rate_class_id')

    op.drop_table('altitude_utility')
    op.drop_table('altitude_supplier')
