"""make charge.target_total double

Revision ID: 42aa3d43db26
Revises: 100f25ab057f
Create Date: 2015-05-18 18:29:06.079936

"""

# revision identifiers, used by Alembic.
revision = '42aa3d43db26'
down_revision = '100f25ab057f'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.alter_column('charge', 'target_total',
               existing_type=mysql.DOUBLE(10, 2),
               nullable=True)


def downgrade():
    op.alter_column('charge', 'target_total',
               existing_type=mysql.FLOAT(),
               nullable=True)
