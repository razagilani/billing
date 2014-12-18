"""creating company table

Revision ID: 1a174da18305
Revises: 39efff02706c
Create Date: 2014-08-11 13:39:35.672182

"""

# revision identifiers, used by Alembic.
revision = '1a174da18305'
down_revision = '37863ab171d1'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('utility',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('address_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.ForeignKeyConstraint(['address_id'], ['address.id'], ),
    sa.PrimaryKeyConstraint('id')
    )



def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('utility')
    ### end Alembic commands ###
