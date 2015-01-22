"""Remove customer table

Revision ID: 3cf530e68eb
Revises: 5a6d7e4f8b80
Create Date: 2015-01-19 10:42:42.863887

"""

# revision identifiers, used by Alembic.
revision = '3cf530e68eb'
down_revision = '5a6d7e4f8b80'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    #op.drop_table('customer')
    #op.drop_column('payment', 'customer_id')
    #op.alter_column('payment', 'reebill_customer_id',
               #existing_type=mysql.INTEGER(display_width=11),
               #nullable=False)
    #op.drop_column('reebill', 'customer_id')
    #op.drop_column('utilbill', 'customer_id')
    ### end Alembic commands ###
    pass


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('utilbill', sa.Column('customer_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.add_column('reebill', sa.Column('customer_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.alter_column('payment', 'reebill_customer_id',
               existing_type=mysql.INTEGER(display_width=11),
               nullable=True)
    op.add_column('payment', sa.Column('customer_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True))
    op.create_table('customer',
    sa.Column('id', mysql.INTEGER(display_width=11), nullable=False),
    sa.Column('name', mysql.VARCHAR(length=45), nullable=False),
    sa.Column('account', mysql.VARCHAR(length=45), nullable=False),
    sa.Column('discountrate', mysql.FLOAT(), nullable=True),
    sa.Column('latechargerate', mysql.FLOAT(), nullable=True),
    sa.Column('bill_email_recipient', mysql.VARCHAR(length=1000), nullable=False),
    sa.Column('service', mysql.ENUM(u'thermal', u'pv'), nullable=True),
    sa.Column('fb_rate_class', mysql.VARCHAR(length=255), nullable=False),
    sa.Column('fb_utility_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('fb_supplier_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.Column('fb_rate_class_id', mysql.INTEGER(display_width=11), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['fb_rate_class_id'], [u'rate_class.id'], name=u'customer_ibfk_2'),
    sa.ForeignKeyConstraint(['fb_supplier_id'], [u'supplier.id'], name=u'customer_ibfk_1'),
    sa.PrimaryKeyConstraint('id'),
    mysql_default_charset=u'utf8',
    mysql_engine=u'InnoDB'
    )
    ### end Alembic commands ###
