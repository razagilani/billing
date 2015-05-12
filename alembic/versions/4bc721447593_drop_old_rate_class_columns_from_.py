"""Drop Old rate_class columns from UtilBill and Customer

Revision ID: 4bc721447593
Revises: 165d171d3a34
Create Date: 2014-10-24 17:44:31.450516

"""

# revision identifiers, used by Alembic.
revision = '4bc721447593'
down_revision = '3566e62e7af3'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_column('customer', 'fb_billing_address_id')
    op.drop_column('customer', 'fb_service_address_id')
    op.drop_constraint('fk_payment_customer', 'payment', 'foreignkey')
    op.drop_constraint('fk_rebill_customer', 'reebill', 'foreignkey')
    op.drop_constraint('fk_utilbill_customer', 'utilbill', 'foreignkey')
    # op.drop_table('customer')
    op.drop_index('fk_utilbill_customer', table_name='utilbill')
    op.drop_index('fk_payment_customer', table_name='payment')
    op.drop_constraint(u'customer_id', 'reebill', 'unique')
    #op.drop_column('utilbill', 'customer_id')
    #op.drop_column('payment', 'customer_id')
    #op.drop_column('reebill', 'customer_id')
    op.create_unique_constraint(u'unq_reebill_customer_id', 'reebill', ['reebill_customer_id', 'sequence', 'version'])
    op.drop_column('utilbill', 'rate_class')


def downgrade():
    SERVICE_TYPES = ('thermal', 'pv')
    '''op.create_table('customer',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=45), nullable=True),
        sa.Column('account', sa.String(length=45), nullable=False),
        sa.Column('discountrate', sa.Float(asdecimal=False), nullable=False),
        sa.Column('latechargerate', sa.Float(asdecimal=False), nullable=False),
        sa.Column('bill_email_recipient', sa.String(length=1000), nullable=False),
        sa.Column('service', sa.Enum(*SERVICE_TYPES), nullable=False),
        sa.Column('fb_rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id')),
        sa.Column('fb_billing_address_id', sa.Integer(), sa.ForeignKey('address.id')),
        sa.Column('fb_service_address_id', sa.Integer(), sa.ForeignKey('address.id')),
        sa.Column('fb_supplier_id', sa.Integer(), sa.ForeignKey('supplier.id')),
        sa.Column('fb_utility_id', sa.Integer(), sa.ForeignKey('company.id')),
        sa.PrimaryKeyConstraint('id'))'''

    op.add_column('customer', sa.Column('fb_billing_address_id', sa.Integer(), sa.ForeignKey('address.id')))
    op.add_column('customer', sa.Column('fb_service_address_id', sa.Integer(), sa.ForeignKey('address.id')))
    op.add_column('customer', sa.Column('fb_rate_class_id', sa.Integer(), sa.ForeignKey('rate_class.id')))
    op.add_column('customer', sa.Column('fb_utility_id', sa.Integer(), sa.ForeignKey('company.id')))
    op.add_column('customer', sa.Column('fb_supplier_id', sa.Integer(), sa.ForeignKey('supplier.id')))
    op.add_column('utilbill', sa.Column('rate_class', sa.String(255), nullable=False))
    op.drop_constraint('reebill_customer_id', 'reebill')
