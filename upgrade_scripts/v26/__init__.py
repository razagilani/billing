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
from core.model import Session, Register

log = logging.getLogger(__name__)

def create_project_manager_role():
    manager_role = Role('Project Manager',
                        'Role for accessing reports view of billentry app')
    return manager_role

def clean_up_register_names(s):
    register_table = Register.__table__
    names = {
        'REG_THERMS': 'REG_TOTAL',

        'REG_ONPEAK': 'REG_PEAK',
        'REG_ON_PK': 'REG_PEAK',

        'REG_INT_PK': 'REG_INTERMEDIATE',
        'REG_INTPEAK': 'REG_INTERMEDIATE',

        'REG_OFF_PK': 'REG_OFFPEAK',

        # what look like "time-of-use demand" meter readings (in only 3
        # bills, none of them processed) are actually just regular demand
        'REG_ONPEAK_DEMAND': 'REG_DEMAND',
        'REG_DEMAND': 'REG_DEMAND',
        'REG_PEAKKW': 'REG_DEMAND',

        'REG_MAX_DEMAND': 'REG_DEMAND',
        'DEMAND_TOTAL': 'REG_DEMAND',

        # bills with blank register_binding are all from 2010 and also have
        # blank "quantity_formula" so charges could not be recalculated anyway
        '': 'REG_TOTAL'
    }
    for old_name, new_name in names.iteritems():
        statement = register_table.update().values(
            register_binding=new_name).where(
            register_table.c.register_binding == old_name)
        s.execute(statement)

def upgrade():
    log.info('Beginning upgrade to version 26')

    init_model(schema_revision='52a7069819cb')
    s = Session()
    clean_up_register_names(s)

    # it is necessary to commit and start a new transaction between changing
    # the data under the old schema and upgrading to the new
    # schema--otherwise MySQL will wait forever. i think this is because the
    # schema-change commands are not part of the transaction, and MySQL wants
    # to wait until all transactions on relevant tables are finished before
    # changing those tables.
    s.commit()

    log.info('upgrading to 100f25ab057f')
    alembic_upgrade('100f25ab057f')

    init_model(schema_revision='100f25ab057f')
    s.add(create_project_manager_role())
    s.commit()


