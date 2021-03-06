"""Added check constraints for utilbill dates

Revision ID: 49b8d9978d7e
Revises: 30597f9f53b9
Create Date: 2015-07-01 13:55:32.895767

"""

# revision identifiers, used by Alembic.
revision = '49b8d9978d7e'
down_revision = '30597f9f53b9'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_check_constraint(
    "ck_period_start",
    "utilbill",
    'period_start > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_period_end",
    "utilbill",
    'period_end > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_next_meter_read_date",
    "utilbill",
    'next_meter_read_date > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_due_date",
    "utilbill",
    'due_date > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_date_received",
    "utilbill",
    'date_received > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_date_modified",
    "utilbill",
    'date_modified > \'1900-01-01\''
    )
    op.create_check_constraint(
    "ck_date_scraped",
    "utilbill",
    'date_scraped > \'1900-01-01\''
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint('ck_date_scraped', 'utilbill', type_='check')
    op.drop_constraint('ck_date_modified', 'utilbill', type_='check')
    op.drop_constraint('ck_date_received', 'utilbill', type_='check')
    op.drop_constraint('ck_due_date', 'utilbill', type_='check')
    op.drop_constraint('ck_next_meter_read_date', 'utilbill', type_='check')
    op.drop_constraint('ck_period_end', 'utilbill', type_='check')
    op.drop_constraint('ck_period_end', 'utilbill', type_='check')
    ### end Alembic commands ###
