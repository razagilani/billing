"""payment application datetime

Revision ID: 3147aa982e03
Revises: 4f2f8e2f7cd
Create Date: 2014-07-23 15:43:12.596865

"""

# revision identifiers, used by Alembic.
revision = '3147aa982e03'
down_revision = '4f2f8e2f7cd'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.types import DateTime, Date


def upgrade():
    op.alter_table('Payment', 'date_applied', type_=DateTime)
    op.alter_table('ReeBill', 'issue_date', type_=DateTime)


def downgrade():
    op.alter_table('Payment', 'date_applied', type_=Date)
    op.alter_table('ReeBill', 'issue_date', type_=Date)

