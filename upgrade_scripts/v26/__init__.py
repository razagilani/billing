"""Upgrade script for version 26.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import logging

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 26')

    init_model(schema_revision='52a7069819cb')
