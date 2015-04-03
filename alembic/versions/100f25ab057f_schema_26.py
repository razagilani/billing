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
    op.add_column('utilbill', sa.Column('tou', sa.Boolean(), nullable=False))
