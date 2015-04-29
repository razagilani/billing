"""schema_27

Revision ID: 3e4ceae0f397
Revises: 100f25ab057f
Create Date: 2015-04-20 16:42:41.513685

"""

# revision identifiers, used by Alembic.
revision = '3e4ceae0f397'
down_revision = '100f25ab057f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table(
        'reebill_user',
        sa.Column('reebill_user_id', sa.Integer(), nullable=False),
        sa.Column('identifier', sa.String(length=100), nullable=False,
                  unique=True),
        sa.Column('username', sa.String(length=1000), nullable=False),
        sa.Column('preferences', sa.String(length=1000), nullable=True),
        sa.Column('session_token', sa.String(length=1000), nullable=True),
        sa.Column('password_hash', sa.String(1000), nullable=False),
        sa.Column('salt', sa.String(1000), nullable=False),
        sa.PrimaryKeyConstraint('reebill_user_id')
    )


