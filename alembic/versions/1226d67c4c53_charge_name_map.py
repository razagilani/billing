"""charge name map

Revision ID: 1226d67c4c53
Revises: 4d54d21b2c7a
Create Date: 2015-08-11 16:29:18.954877

"""

# revision identifiers, used by Alembic.
revision = '1226d67c4c53'
down_revision = '4d54d21b2c7a'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('charge_name_map',
        sa.Column('charge_name_map_id', sa.Integer(), primary_key=True),
        sa.Column('display_name_regex', sa.String(), nullable=False),
        sa.Column('reviewed', sa.Boolean(), nullable=False),
        sa.Column('rsi_binding', sa.String(), nullable=False))


def downgrade():
    raise NotImplementedError
