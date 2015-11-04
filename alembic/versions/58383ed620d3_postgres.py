"""postgres

Things that need to be cleaned up in MySQL in preparation for migrating to
PostgreSQL.

Revision ID: 58383ed620d3
Revises: 52a7069819cb
Create Date: 2015-03-12 15:02:51.153207

"""

# revision identifiers, used by Alembic.
from core.model import Register

revision = '58383ed620d3'
down_revision = 'a583e412020'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('reebill', 'issued', existing_type=sa.Integer,
                    type_=sa.Boolean)
    op.alter_column('reading', 'register_binding',
                    existing_type=sa.String(length=1000),
                    type_=Register.register_binding_type)

def downgrade():
    op.alter_column('reebill', 'issued', existing_type=sa.Boolean,
                    type_=sa.Integer)

