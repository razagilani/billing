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
    sa.Column('company_id', sa.Integer(), sa.ForeignKey('company.id')),
    sa.PrimaryKeyConstraint('id'))
    op.add_column('utilbill',
    sa.Column('supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id')))
    op.add_column('customer',
        sa.Column('fb_supplier_id', sa.INTEGER, sa.ForeignKey('supplier.id'))
    )

    op.add_column('utilbill', sa.Column('date_scraped', sa.DateTime,
                                        nullable=True))
    op.create_table('rate_class',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('utility_id', sa.Integer(),sa.ForeignKey('company.id')),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('customer', sa.Column('fb_rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id')))
    op.add_column('utilbill', sa.Column('rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id')))

    # tables for foreign keys to Altitude (many-to-1 with utility and supplier)
    # TODO: move this to somewhere after the utility/supplier tables exist and
    # the company table doesn't?
    op.create_table('altitude_utility',
                    sa.Column('id', sa.Integer(), primary_key=True,
                              nullable=False),
                    sa.Column('utility_id', sa.Integer(),
                              sa.ForeignKey('company.id'), nullable=False),
                    sa.Column('guid', sa.String(length=35), nullable=False))
    op.create_table('altitude_supplier',
                    sa.Column('id', sa.Integer(), primary_key=True,
                              nullable=False),
                    sa.Column('supplier_id', sa.Integer(),
                              sa.ForeignKey('supplier.id'), nullable=False),
                    sa.Column('guid', sa.String(length=35), nullable=False))
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
