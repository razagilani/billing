"""bill validation

Revision ID: 3482c138b392
Revises: 4d54d21b2c7a
Create Date: 2015-08-17 13:32:34.882940

"""

# revision identifiers, used by Alembic.
from core.model import UtilBill

revision = '3482c138b392'
down_revision = '4d54d21b2c7a'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # # apparently "alter type" to add values to an enum doesn't work in
    # # Alembic, so you can't use op.alter_column(..., type_=...)
    # # https://bitbucket.org/zzzeek/alembic/issue/270/altering-enum-type
    # # AND postgres won't let you run "alter type" inside a transaction either.
    # # https://bitbucket.org/zzzeek/alembic/issue/123/a-way-to-run-non-transactional-ddl
    # connection = op.get_bind()
    # connection.execution_options(isolation_level='AUTOCOMMIT')
    # for value in UtilBill.VALIDATION_STATES:
    #     op.execute("alter type validation_state add value '%s'" % value)

    validation_state_enum = sa.Enum(*UtilBill.VALIDATION_STATES,
        name='validation_state')
    validation_state_enum.create(op.get_bind(), checkfirst=False)
    op.add_column('utilbill', sa.Column('validation_state',
        validation_state_enum, server_default=UtilBill.FAILED))


def downgrade():
    pass
