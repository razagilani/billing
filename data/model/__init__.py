"""Longer-term move the SQLAlchemy model objects defined in the 
:module:`billing.processing.state` module into this file,
since they belong to a wider scope than just within
:module:`billing.processing`.
"""
from alembic.migration import MigrationContext
from billing.exc import DatabaseError
from billing.data.model.orm import Session, Base
import logging

#_schema_revision = '2a89489227e'
_schema_revision = None

log = logging.getLogger(__name__)

def check_schema_revision(schema_revision=_schema_revision):
    """Checks to see whether the database schema revision matches the
    revision expected by the model metadata.
    """
    s = Session()
    conn = s.connection()
    context = MigrationContext.configure(conn)
    current_revision = context.get_current_revision()
    if current_revision != schema_revision:
        raise DatabaseError("Database schema revision mismatch."
                            " Require revision %s; current revision %s"
                            % (schema_revision, current_revision))
    log.debug('Verified database at schema revision %s' % current_revision)

from billing.processing.state import *
from .brokerage import *
from .company import *
from .auth import *
