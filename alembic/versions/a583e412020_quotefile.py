"""quotefile

Revision ID: a583e412020
Revises: 100f25ab057f
Create Date: 2015-04-21 14:01:47.713255

"""

# revision identifiers, used by Alembic.
revision = 'a583e412020'
down_revision = '3e4ceae0f397'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table(
        'quote',
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.Column('start_from', sa.Integer(), nullable=False),
        sa.Column('start_until', sa.Integer(), nullable=False),
        sa.Column('term_months', sa.Integer(), nullable=False),
        sa.Column('date_received', sa.DateTime(), nullable=False),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('discriminator', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('quote_id')
    )
    op.create_table(
        'matrix_quote',
        sa.Column('min_volume', sa.Float(), nullable=True),
        sa.Column('limit_volume', sa.Float(), nullable=True),
        sa.Column('quote_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['quote_id'], ['quote.quote_id'], ),
        sa.PrimaryKeyConstraint('quote_id')
    )
