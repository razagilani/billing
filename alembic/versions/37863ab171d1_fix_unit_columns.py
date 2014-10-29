"""fix_unit_columns

Revision ID: 37863ab171d1
Revises: 3566e62e7af3
Create Date: 2014-10-16 10:42:08.387049

"""

# revision identifiers, used by Alembic.
revision = '37863ab171d1'
down_revision = '6446c51511c'

from alembic import op
import sqlalchemy as sa

def upgrade():
    # note empty string is no longer a valid unit
    units = [
        'kWh',
        'dollars',
        'KWD',
        'therms',
        'MMBTU',
        'BTU',
    ]
    op.alter_column('register', 'quantity_units', new_column_name='unit',
                    type_=sa.Enum(*units), nullable=False)
    op.alter_column('charge', 'quantity_units', new_column_name='unit',
                    type_=sa.Enum(*units))
    op.alter_column('reading', 'unit', type_=sa.Enum(*units))
    op.alter_column('reebill_charge', 'quantity_unit', new_column_name='unit',
                    type_=sa.Enum(*units))

def downgrade():
    raise NotImplemented

