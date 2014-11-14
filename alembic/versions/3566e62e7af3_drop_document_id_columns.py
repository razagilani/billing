"""drop document ID columns

Revision ID: 3566e62e7af3
Revises: 18a02dea5969
Create Date: 2014-10-01 11:33:58.403780

"""

# revision identifiers, used by Alembic.
revision = '3566e62e7af3'
down_revision = '18a02dea5969'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.drop_column('utilbill_reebill', 'document_id')
    op.drop_column('utilbill_reebill', 'uprs_document_id')
    op.drop_column('utilbill_reebill', 'cprs_document_id')
    op.drop_column('utilbill', 'document_id')
    op.drop_column('utilbill', 'uprs_document_id')
    op.drop_column('utilbill', 'cprs_document_id')

def downgrade():
    op.add_column('utilbill_reebill', sa.Column('document_id',
            mysql.VARCHAR(length=24), nullable=True))
    op.add_column('utilbill_reebill', sa.Column('uprs_document_id',
        mysql.VARCHAR(length=24), nullable=True))
    op.add_column('utilbill_reebill', sa.Column('cprs_document_id',
        mysql.VARCHAR(length=24), nullable=True))
    op.add_column('utilbill', sa.Column('document_id',
        mysql.VARCHAR(length=24), nullable=True))
    op.add_column('utilbill', sa.Column('uprs_document_id',
        mysql.VARCHAR(length=24), nullable=True))
    op.add_column('utilbill', sa.Column('cprs_document_id',
        mysql.VARCHAR(length=24), nullable=True))

