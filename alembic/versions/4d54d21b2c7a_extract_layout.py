"""extract_layout

Revision ID: 4d54d21b2c7a
Revises: 49b8d9978d7e
Create Date: 2015-07-06 17:22:56.906735

"""

# revision identifiers, used by Alembic.
from sqlalchemy.dialects.postgresql import HSTORE

revision = '4d54d21b2c7a'
down_revision = '49b8d9978d7e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # apparently "alter type" to add values to an enum doesn't work in
    # Alembic, so you can't use op.alter_column(..., type_=...)
    # https://bitbucket.org/zzzeek/alembic/issue/270/altering-enum-type
    # AND postgres won't let you run "alter type" inside a transaction either.
    # https://bitbucket.org/zzzeek/alembic/issue/123/a-way-to-run-non-transactional-ddl
    connection = op.get_bind()
    connection.execution_options(isolation_level='AUTOCOMMIT')
    new_type_names = [
        'table charges',
    ]
    import ipdb; ipdb.set_trace()
    for value in new_type_names:
        op.execute("alter type field_type add value '%s'" % value)

    op.add_column('extractor', sa.Column('origin_regex', sa.String()))
    op.add_column('extractor', sa.Column('origin_x', sa.Float()))
    op.add_column('extractor', sa.Column('origin_y', sa.Float()))

    op.alter_column('field', 'regex', nullable=True)

    op.add_column('field', sa.Column('bbregex', sa.String))
    op.add_column('field', sa.Column('offset_regex', sa.String))
    op.add_column('field', sa.Column('corner', sa.Integer()))
    op.add_column('field', sa.Column('multipage_table', sa.Boolean()))
    op.add_column('field', sa.Column('maxpage', sa.Integer()))
    op.add_column('field', sa.Column('nextpage_top', sa.Float()))
    op.add_column('field', sa.Column('table_start_regex', sa.String))
    op.add_column('field', sa.Column('table_stop_regex', sa.String))

    op.add_column('extractor_result', sa.Column('field_period_total', HSTORE()))
    op.add_column('extractor_result',
                  sa.Column('period_total_by_month', HSTORE()))

def downgrade():
    pass
