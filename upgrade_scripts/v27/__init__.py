"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.model import Session, UtilBill
from core.model.model import SupplyGroup

from upgrade_scripts import alembic_upgrade
from core import init_model

log = logging.getLogger(__name__)

def create_and_assign_supply_groups(s):
    bills = s.query(UtilBill).all()
    for bill in bills:
        supply_group = SupplyGroup('SOSGroup', bill['supplier'], bill.get_service())
        s.add(supply_group)

def upgrade():
    log.info('Beginning upgrade to version 27')
