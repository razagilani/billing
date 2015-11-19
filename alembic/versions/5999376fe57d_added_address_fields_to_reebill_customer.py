"""added address fields to reebill_customer

Revision ID: 5999376fe57d
Revises: 127c3e14d9d4
Create Date: 2015-11-19 11:35:01.363490

"""

# revision identifiers, used by Alembic.
revision = '5999376fe57d'
down_revision = '127c3e14d9d4'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('reebill_customer', sa.Column('billing_address_id', sa.Integer(), nullable=True))
    op.add_column('reebill_customer', sa.Column('service_address_id', sa.Integer(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('reebill_customer', 'service_address_id')
    op.drop_column('reebill_customer', 'billing_address_id')
    ### end Alembic commands ###
