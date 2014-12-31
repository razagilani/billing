"""create utility_account table

Revision ID: 507c0437a7f8
Revises: 4bc721447593
Create Date: 2014-11-05 14:42:24.732669

"""

# revision identifiers, used by Alembic.
revision = '507c0437a7f8'
down_revision = 'fc9faca7a7f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    SERVICE_TYPES = ('thermal', 'pv')
    op.create_table('utility_account',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=45), nullable=True),
        sa.Column('account', sa.String(length=45), unique=True, nullable=False),
        sa.Column('account_number', sa.String(length=1000), nullable=False),
        sa.Column('fb_rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id'), nullable=True),
        sa.Column('fb_billing_address_id', sa.Integer(), sa.ForeignKey('address.id')),
        sa.Column('fb_service_address_id', sa.Integer(), sa.ForeignKey('address.id')),
        sa.Column('fb_supplier_id', sa.Integer(), sa.ForeignKey('supplier.id'), nullable=True),
        sa.Column('fb_utility_id', sa.Integer(), sa.ForeignKey('utility.id')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('reebill_customer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=45), nullable=True),
        sa.Column('discountrate', sa.Float(asdecimal=False), nullable=False),
        sa.Column('latechargerate', sa.Float(asdecimal=False), nullable=False),
        sa.Column('bill_email_recipient', sa.String(length=1000), nullable=False),
        sa.Column('service', sa.Enum(*SERVICE_TYPES), nullable=False),
        sa.Column('utility_account_id', sa.Integer(), sa.ForeignKey('utility_account.id')),
        sa.PrimaryKeyConstraint('id')
    )
    #op.drop_column('utilbill', 'customer_id')
    op.add_column('utilbill', sa.Column('utility_account_id', sa.Integer(), sa.ForeignKey('utility_account.id')))
    op.add_column('payment', sa.Column('reebill_customer_id', sa.Integer(), sa.ForeignKey('reebill_customer.id')))
    op.add_column('reebill', sa.Column('reebill_customer_id', sa.Integer(), sa.ForeignKey('reebill_customer.id')))
    op.alter_column('payment', 'customer_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('utilbill', 'customer_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('reebill', 'customer_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('customer', 'fb_billing_address_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('customer', 'fb_service_address_id', existing_type=sa.Integer(), nullable=True)
    op.execute('drop view status_days_since')
    op.execute('drop view status_unbilled')

    op.create_table('altitude_account',
        sa.Column('utility_account_id', sa.Integer(),
                            sa.ForeignKey('utility_account.id'),
                            nullable=False),
        sa.Column('guid', sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint('utility_account_id', 'guid'))

def downgrade():
    op.drop_table('utility_account')
    op.drop_table('reebill_customer')
    op.add_column('utilbill', sa.Column('customer_id', sa.Integer(), sa.ForeignKey('customer.id')))
    op.drop_column('utilbill', 'utility_account_id')
    op.drop_column('payment', 'reebill_customer_id')
    op.drop_column('reebill', 'reebill_customer_id')
    op.alter_column('payment', 'customer_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('utilbill', 'customer_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('reebill', 'customer_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('customer', 'fb_billing_address_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('customer', 'fb_service_address_id', existing_type=sa.Integer(), nullable=False)
    op.drop_table('altitude_account')
