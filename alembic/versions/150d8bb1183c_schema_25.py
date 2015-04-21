"""schema_25

Revision ID: 150d8bb1183c
Revises: 2d65c7c19345
Create Date: 2015-02-17 13:33:37.516374

Put all schema changes related to version 25 in here, if possible--let's try
not to add too many individual Alembic scripts.
"""

# revision identifiers, used by Alembic.
revision = '150d8bb1183c'
down_revision = '2d65c7c19345'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.create_table('billentry_user',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('password', sa.String(length=60), nullable=False),
                    sa.Column('email', sa.String(length=50), nullable=False),
                    sa.Column('registered_on', sa.DateTime(), nullable=False),
                    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_billentry_users_email'), 'billentry_user', ['email'], unique=True)
    op.add_column(u'utilbill', sa.Column('billentry_date', sa.DateTime()))
    op.add_column(u'utilbill', sa.Column('billentry_user_id', sa.Integer(),
                                         sa.ForeignKey('billentry_user.id')))
    op.add_column(u'utilbill', sa.Column('discriminator', sa.String(1000),
                                         nullable=False))
    op.add_column(u'utilbill', sa.Column('next_meter_read_date', sa.Date()))
    op.drop_column(u'charge', 'group')
    op.alter_column(u'reebill_charge', 'group_name', new_column_name='type',
                    existing_type=sa.String(1000))

def downgrade():
    op.drop_column(u'utilbill', 'discriminator')
    op.drop_column(u'utilbill', 'billentry_user_id')
    op.drop_column(u'utilbill', 'billentry_date')
    op.drop_index(op.f('ix_billentry_users_email'), table_name='billentry_users')
    op.drop_table('billentry_user')

    # to downgrade, value could be approximately restored by copying the
    # value of "type"
    op.add_column(u'charge', 'group')

    op.alter_column(u'reebill_charge', 'type', new_column_name='group_name',
                    existing_type=sa.String(1000))

