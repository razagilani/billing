"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
import os
import subprocess

from brokerage.brokerage_model import MatrixFormat
from core.model import Session, AltitudeSession, Supplier, Base
from core import init_model, get_db_params, init_altitude_db
from upgrade_scripts import alembic_upgrade

log = logging.getLogger(__name__)

def upgrade():
    alembic_upgrade('4f589e8d4cab')

    init_model()
    Base.metadata.reflect()
    s = Session()

    # create MatrixFormat objects, which now contain the
    # matrix_attachment_name column.
    # the Supplier.matrix_attachment_name attribute removed but the
    # supplier.matrix_attachement_name column still exists in the database. i
    # couldn't figure out the fancy SQLAlchemy way to add such a hidden
    # column to the query, so:
    cur = s.execute("select name, id, matrix_attachment_name from supplier "
                    "where matrix_email_recipient is not null")
    for name, supplier_id, matrix_attachment_name in cur.fetchall():
        s.add(MatrixFormat(name=name, supplier_id=supplier_id,
                           matrix_attachment_name=matrix_attachment_name))
        log.info('Created MatrixFormat for supplier %s "%s"' % (
            supplier_id, name))
    s.commit()
