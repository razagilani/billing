"""create unique indices on name column on supplier, utility, rate_class

Revision ID: 5a02ad84f437
Revises: 5a6d7e4f8b80
Create Date: 2015-01-02 17:37:21.169025

"""

# revision identifiers, used by Alembic.
revision = '5a02ad84f437'
down_revision = '5a6d7e4f8b80'

from alembic import op
import sqlalchemy as sa


def upgrade():
     op.create_unique_constraint("uq_utility_name", "utility", ["name"])
     op.create_unique_constraint("uq_supplier_name", "supplier", ["name"])
     op.create_unique_constraint("uq_rate_class_name", "rate_class", ["name"])

def downgrade():
    op.drop_constraint("uq_utility_name", "utility", 'unique')
    op.drop_constraint("uq_supplier_name", "supplier", 'unique')
    op.drop_constraint("uq_rate_class_name", "rate_class", 'unique')
