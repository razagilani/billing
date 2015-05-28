"""extract

Revision ID: 30597f9f53b9
Revises: 58383ed620d3
Create Date: 2015-05-22 13:20:06.676570

"""

# revision identifiers, used by Alembic.
revision = '30597f9f53b9'
down_revision = '58383ed620d3'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects import postgresql

def upgrade():
    op.create_table('extractor',
                    sa.Column('extractor_id', sa.Integer(), nullable=False),
                    sa.Column('discriminator', sa.String(), nullable=False),
                    sa.Column('name', sa.String(), nullable=False),
                    sa.PrimaryKeyConstraint('extractor_id')
    )
    op.create_table('field',
                    sa.Column('field_id', sa.Integer(), nullable=False),
                    sa.Column('discriminator', sa.String(), nullable=False),
                    sa.Column('extractor_id', sa.Integer(), nullable=True),
                    sa.Column('type', sa.Enum('date', 'wg charges', 'float', 'string', name='field_type'), nullable=True),
                    sa.Column('applier_key', sa.Enum('charges', 'next read', 'energy', 'end', 'start', name='applier_key'), nullable=True),
                    sa.Column('regex', sa.String(), nullable=False),
                    sa.ForeignKeyConstraint(['extractor_id'], ['extractor.extractor_id'], ),
                    sa.PrimaryKeyConstraint('field_id'),
                    sa.UniqueConstraint('extractor_id', 'applier_key')
                    )
    op.add_column(u'charge', sa.Column('name', sa.String(), nullable=True))
    op.add_column(u'utilbill', sa.Column('text', sa.String(), nullable=True))
    op.add_column(u'utility', sa.Column('charge_name_map', postgresql.HSTORE(), nullable=False, server_default=''))


def downgrade():
    raise NotImplementedError
