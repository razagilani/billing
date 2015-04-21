"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.model import Session

from upgrade_scripts import alembic_upgrade
from core import init_model
from upgrade_scripts.v27.create_register_templates import \
    create_register_templates

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 27')
    init_model()
    s = Session()
    create_register_templates(s, log)
