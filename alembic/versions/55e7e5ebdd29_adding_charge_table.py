"""adding charge table

Revision ID: 55e7e5ebdd29
Revises: None
Create Date: 2014-05-13 16:26:37.191327

"""

# revision identifiers, used by Alembic.
revision = '55e7e5ebdd29'
down_revision = None

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table('charge',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('group', sa.String(length=255), nullable=True),
    sa.Column('utilbill_id', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('quantity_units', sa.String(length=255), nullable=True),
    sa.Column('rate', sa.Float(), nullable=True),
    sa.Column('rsi_binding', sa.String(length=255), nullable=True),
    sa.Column('total', sa.Float(), nullable=True),
    sa.Column('error', sa.String(255), nullable=True),
    sa.ForeignKeyConstraint(['utilbill_id'], ['utilbill.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    
def downgrade():
    op.drop_table('charge')
