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
                    sa.Column('created', sa.DateTime(), nullable=False,
                              server_default=sa.func.now()),
                    sa.Column('modified', sa.DateTime(), nullable=False,
                              server_default=sa.func.now(),
                              onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint('extractor_id')
    )
    op.create_table('field',
        sa.Column('field_id', sa.Integer(), nullable=False),
                    sa.Column('discriminator', sa.String(), nullable=False),
        sa.Column('extractor_id', sa.Integer(), nullable=True),
        sa.Column('type',
            sa.Enum('address', 'date', 'wg charges', 'float', 'string', 'pepco old charges', 'pepco new charges',
                name='field_type'), nullable=True),
        sa.Column('applier_key', sa.Enum('billing address', 'charges', 'next read', 'energy', 'end', 'service address', 'start', name='applier_key'),
            nullable=True),
        sa.Column('regex', sa.String(length=1000), nullable=False),
        sa.ForeignKeyConstraint(['extractor_id'], ['extractor.extractor_id'], ),
        sa.PrimaryKeyConstraint('field_id'),
        sa.UniqueConstraint('extractor_id', 'applier_key')
    )
    op.add_column(u'charge', sa.Column('name', sa.String(), nullable=True))
    op.add_column(u'utilbill', sa.Column('text', sa.String(), nullable=True))
    op.add_column(u'utility', sa.Column('charge_name_map', postgresql.HSTORE(), nullable=False, server_default=''))
    op.create_table('extractor_result',
        sa.Column('extractor_result_id', sa.Integer(), primary_key=True),
        sa.Column('task_id', sa.String(), nullable=False),
        sa.Column('extractor_id', sa.Integer(), sa.ForeignKey('extractor.extractor_id')),
        sa.Column('started', sa.DateTime(), nullable=False),
        sa.Column('finished', sa.DateTime()),
        sa.Column('utility_id', sa.Integer(), sa.ForeignKey('utility.id')),
        sa.Column('all_count', sa.Integer()),
        sa.Column('any_count', sa.Integer()),
        sa.Column('total_count', sa.Integer()),
        sa.Column('field_charges', sa.Integer()),
        sa.Column('field_next_read', sa.Integer()),
        sa.Column('field_energy', sa.Integer()),
        sa.Column('field_start', sa.Integer()),
        sa.Column('field_end', sa.Integer()),
        sa.Column('charges_by_month', postgresql.HSTORE()),
        sa.Column('next_read_by_month', postgresql.HSTORE()),
        sa.Column('energy_by_month', postgresql.HSTORE()),
        sa.Column('start_by_month', postgresql.HSTORE()),
        sa.Column('end_by_month', postgresql.HSTORE()))

def downgrade():
    raise NotImplementedError
