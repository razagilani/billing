"""schema 26

Revision ID: 100f25ab057f
Revises: 23a21392b372
Create Date: 2015-03-24 14:40:47.367423

"""

# revision identifiers, used by Alembic.
revision = '100f25ab057f'
down_revision = '52a7069819cb'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    # some differences that Alembic found between the class definitions and
    # the database
    op.create_index(op.f('ix_billentry_user_email'), 'billentry_user',
                    ['email'], unique=True)
    op.alter_column(u'charge', 'type',
               existing_type=mysql.ENUM(u'supply', u'distribution'),
               nullable=False)
    op.drop_column(u'reebill', 'customer_id')
    op.alter_column(u'reebill_charge', 'type',
                    existing_type=mysql.VARCHAR(length=1000), nullable=False)
    op.drop_column(u'utilbill', 'customer_id')

    op.create_table('customer_group',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('name', sa.String(length=1000), nullable=False),
                    sa.Column('bill_email_recipient', sa.String(length=1000),
                              nullable=False), sa.PrimaryKeyConstraint('id'))
    op.create_table('customer_customer_group',
                    sa.Column('reebill_customer_id', sa.Integer(),
                              nullable=False),
                    sa.Column('customer_group_id', sa.Integer(),
                              nullable=False),
                    sa.ForeignKeyConstraint(['customer_group_id'],
                                            ['customer_group.id'],
                                            ondelete='cascade'),
                    sa.ForeignKeyConstraint(['reebill_customer_id'],
                                            ['reebill_customer.id'],
                                            ondelete='cascade'),
                    sa.PrimaryKeyConstraint('reebill_customer_id',
                                            'customer_group_id'))
    op.alter_column('billentry_role', 'name',
               existing_type=mysql.VARCHAR(length=10),
               type_=mysql.VARCHAR(length=20))

    op.add_column(u'utilbill', sa.Column('flagged', sa.Boolean()))
    op.add_column('utilbill', sa.Column('tou', sa.Boolean(), nullable=False))
    
    # can't import this from model.py
    PHYSICAL_UNITS = [
        'BTU',
        'MMBTU',
        'kWD',
        'kWh',
        'therms',
    ]
    REGISTER_BINDINGS = [
        'REG_TOTAL',
        'REG_TOTAL_SECONDARY',
        'REG_TOTAL_TERTIARY',
        'REG_PEAK',
        'REG_INTERMEDIATE',
        'REG_OFFPEAK',
        'REG_DEMAND',
        'REG_POWERFACTOR',

        'REG_PEAK_RATE_INCREASE',
        'REG_INTERMEDIATE_RATE_INCREASE',
        'REG_OFFPEAK_RATE_INCREASE',
        'FIRST_MONTH_THERMS',
        'SECOND_MONTH_THERMS',

        'BEGIN_INVENTORY',
        'END_INVENTORY',
        'CONTRACT_VOLUME',
    ]

    op.create_table('register_template',
        sa.Column('register_template_id', sa.Integer, primary_key=True),
        sa.Column('rate_class_id', sa.Integer, sa.ForeignKey('rate_class.id'),
                  nullable=False),
        sa.Column('register_binding', sa.Enum(*REGISTER_BINDINGS),
                  nullable=False),
        sa.Column('unit', sa.Enum(*PHYSICAL_UNITS), nullable=False),
        sa.Column('active_periods', sa.String(2048)),
        sa.Column('description', sa.String(255), nullable=False, default=''))

    op.alter_column('register', 'register_binding',
                    existing_type=sa.String(length=1000),
                    type_=sa.Enum(*REGISTER_BINDINGS))

    # creation of unique constraint for register table will fail due to
    # existing duplicate values. these can be deleted using "alter ignore table"
    # in MySQL though Alembic does not seem to support that.
    # there are 24 duplicate registers in 5 bills, all of which have empty
    # register_binding
    op.execute("alter ignore table register add unique index "
               "(utilbill_id, register_binding)")
    op.create_unique_constraint(None, 'register_template',
                                ['rate_class_id', 'register_binding'])