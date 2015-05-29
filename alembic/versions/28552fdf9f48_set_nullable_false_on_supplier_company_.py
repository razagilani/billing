"""set nullable=False on supplier.company_id, rate_class.utility_id, company.name, and company.discriminator

Revision ID: 28552fdf9f48
Revises: 32b0a5fe5074
Create Date: 2014-12-10 15:54:02.791676

"""

# revision identifiers, used by Alembic.
revision = '28552fdf9f48'
down_revision = '32b0a5fe5074'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


def upgrade():
    op.alter_column(u'rate_class', 'utility_id',
           existing_type=mysql.INTEGER(display_width=11),
           nullable=False)

def downgrade():
    op.alter_column(u'rate_class', 'utility_id',
           existing_type=mysql.INTEGER(display_width=11),
           nullable=True)

