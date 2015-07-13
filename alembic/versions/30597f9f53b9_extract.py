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
    log = logging.getLogger('alembic')

    # create HSTORE extension if possible. only superusers can do this. if
    # the user is not a superuser, this error will be ignored, but creation
    # of columns with the type HSTORE below will fail instead.
    try:
        op.execute('create extension if not exists hstore')
    except ProgrammingError:
        log.info('failed to create extension HSTORE')

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
            sa.Enum('address', 'date', 'float', 'pepco old charges', 'pepco new charges', 'rate class', 'string', 'wg charges',
                name='field_type'), nullable=True),
        sa.Column('applier_key', sa.Enum('billing address', 'charges', 'rate class', 'next read', 'energy', 'end', 'service address', 'start', name='applier_key'),
            nullable=True),
        sa.Column('regex', sa.String(length=1000), nullable=False),
        sa.Column('page_num', sa.Integer()),
        sa.Column('bbminx', sa.Float(), nullable=True),
        sa.Column('bbminy', sa.Float(), nullable=True),
        sa.Column('bbmaxx', sa.Float(), nullable=True),
        sa.Column('bbmaxy', sa.Float(), nullable=True),
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
        sa.Column('parent_id', sa.String(), nullable=False),
        sa.Column('extractor_id', sa.Integer(), sa.ForeignKey('extractor.extractor_id')),
        sa.Column('bills_to_run', sa.Integer(), nullable=False),
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
        sa.Column('field_rate_class', sa.Integer()),
        sa.Column('field_service_address', sa.Integer()),
        sa.Column('field_start', sa.Integer()),
        sa.Column('billing_address_by_month', postgresql.HSTORE()),
        sa.Column('charges_by_month', postgresql.HSTORE()),
        sa.Column('end_by_month', postgresql.HSTORE()),
        sa.Column('energy_by_month', postgresql.HSTORE()),
        sa.Column('next_read_by_month', postgresql.HSTORE()),
        sa.Column('rate_class_by_month', postgresql.HSTORE()),
        sa.Column('service_address_by_month', postgresql.HSTORE()),
        sa.Column('start_by_month', postgresql.HSTORE()),

        sa.Column('processed_count', sa.Integer()),
        sa.Column('field_billing_address_correct', sa.Integer()),
        sa.Column('field_charges_correct', sa.Integer()),
        sa.Column('field_end_correct', sa.Integer()),
        sa.Column('field_energy_correct', sa.Integer()),
        sa.Column('field_next_read_correct', sa.Integer()),
        sa.Column('field_rate_class_correct', sa.Integer()),
        sa.Column('field_service_address_correct', sa.Integer()),
        sa.Column('field_start_correct', sa.Integer()),)

def downgrade():
    raise NotImplementedError
