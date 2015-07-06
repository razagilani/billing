"""extract

Revision ID: 30597f9f53b9
Revises: 58383ed620d3
Create Date: 2015-05-22 13:20:06.676570

"""

# revision identifiers, used by Alembic.
import logging
from sqlalchemy.exc import ProgrammingError

revision = '30597f9f53b9'
down_revision = '14c726a1ee30'

from alembic import op
import sqlalchemy as sa
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
        sa.Column('origin_regex', sa.String()),
        sa.Column('origin_x', sa.Float()),
        sa.Column('origin_y', sa.Float()),
        sa.PrimaryKeyConstraint('extractor_id')
    )
    op.create_table('field',
        sa.Column('field_id', sa.Integer(), nullable=False),
                    sa.Column('discriminator', sa.String(), nullable=False),
        sa.Column('extractor_id', sa.Integer(), nullable=True),
        sa.Column('type',
            sa.Enum('address', 'date', 'float', 'pepco old charges',
                'pepco new charges', 'rate class', 'string', 'table charges',
                'wg charges',
                name='field_type'), nullable=True),
        sa.Column('applier_key',
            sa.Enum('billing address', 'charges', 'energy', 'end', 'next read',
                'period total', 'rate class', 'service address', 'start',
                name='applier_key'),
            nullable=True),
        sa.Column('regex', sa.String(length=1000)),
        sa.Column('bbregex', sa.String(length=1000)),
        sa.Column('offset_regex', sa.String(length=1000)),
        sa.Column('page_num', sa.Integer()),
        sa.Column('bbminx', sa.Float(), nullable=True),
        sa.Column('bbminy', sa.Float(), nullable=True),
        sa.Column('bbmaxx', sa.Float(), nullable=True),
        sa.Column('bbmaxy', sa.Float(), nullable=True),
        sa.Column('corner', sa.Integer(), nullable=True),
        sa.Column('multipage_table', sa.Boolean(), nullable=True),
        sa.Column('maxpage', sa.Integer(), nullable=True),
        sa.Column('nextpage_top', sa.Float(), nullable=True),
        sa.Column('table_start_regex', sa.String(length=1000)),
        sa.Column('table_stop_regex', sa.String(length=1000)),
        # multipage_table = Column(Boolean)
        # # For multi-page tables, the last page to which  the table extends.
        # maxpage = Column(Integer)
        # # For multi-page tables, the y-value at which the table starts,
        # # on subsequent pages. i.e. the top margin.
        # nextpage_top = Column(Float)
        # # For multi-page tables, the y-value at which the table stops,
        # # on subsequent pages. i.e. the bottom margin.
        # nextpage_bottom = Column(Float)
        # # A regex that matches a text object that comes after the end of the
        # # table. This is for tables whose ending y-value varies.
        # table_stop_regex = Column(String)
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
        sa.Column('field_billing_address', sa.Integer()),
        sa.Column('field_charges', sa.Integer()),
        sa.Column('field_end', sa.Integer()),
        sa.Column('field_energy', sa.Integer()),
        sa.Column('field_next_read', sa.Integer()),
        sa.Column('field_period_total', sa.Integer()),
        sa.Column('field_rate_class', sa.Integer()),
        sa.Column('field_service_address', sa.Integer()),
        sa.Column('field_start', sa.Integer()),
        sa.Column('billing_address_by_month', postgresql.HSTORE()),
        sa.Column('charges_by_month', postgresql.HSTORE()),
        sa.Column('end_by_month', postgresql.HSTORE()),
        sa.Column('energy_by_month', postgresql.HSTORE()),
        sa.Column('next_read_by_month', postgresql.HSTORE()),
        sa.Column('period_total_by_month', postgresql.HSTORE()),
        sa.Column('rate_class_by_month', postgresql.HSTORE()),
        sa.Column('service_address_by_month', postgresql.HSTORE()),
        sa.Column('start_by_month', postgresql.HSTORE()))

def downgrade():
    raise NotImplementedError
