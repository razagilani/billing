"""schema_25

Revision ID: 44260b6956b7
Revises: 2d65c7c19345
Create Date: 2015-02-16 19:12:42.695641

"""

# revision identifiers, used by Alembic.
revision = '44260b6956b7'
down_revision = '2d65c7c19345'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table('billentry_user',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('billentry_event',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('utilbill_id', sa.Integer(), nullable=False),
                    sa.Column('date', sa.DateTime(), nullable=False),
                    sa.Column('billentry_user_id', sa.Integer(), nullable=False),
                    sa.ForeignKeyConstraint(['billentry_user_id'], ['billentry_user.id'], ),
                    sa.ForeignKeyConstraint(['utilbill_id'], ['utilbill.id'], ),
                    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('billentry_event')
    op.drop_table('billentry_user')
