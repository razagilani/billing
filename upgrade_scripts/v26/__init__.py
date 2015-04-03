"""Upgrade script for version 26.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import logging
from billentry.billentry_model import Role
from core.model.model import RegisterTemplate

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session, RateClass

log = logging.getLogger(__name__)

def create_project_manager_role(s):
    s.add(Role('Project Manager',
                        'Role for accessing reports view of billentry app'))

def create_register_templates(s):
    for rate_class in s.query(RateClass).all():
        unit = 'therms' if rate_class.service == 'gas' else 'kWh'
        rate_class.register_templates.append(
            RegisterTemplate.get_total_register_template(unit))

def upgrade():
    log.info('Beginning upgrade to version 26')

    log.info('upgrading to 100f25ab057f')
    alembic_upgrade('100f25ab057f')

    init_model(schema_revision='100f25ab057f')
    s = Session()
    create_project_manager_role(s)
    create_register_templates(s)
    s.commit()


