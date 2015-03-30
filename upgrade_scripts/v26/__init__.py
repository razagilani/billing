"""Upgrade script for version 26.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import logging
from billentry.billentry_model import Role

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 26')

    alembic_upgrade('100f25ab057f')

    log.info('upgrading to 44b3d2dcc1d3')
    alembic_upgrade('44b3d2dcc1d3')

    s = Session()
    s.add(create_project_manager_role())
    s.commit()


def create_project_manager_role():
    manager_role = Role('Project Manager', 'Role for accessing reports view of billentry app')
    return manager_role