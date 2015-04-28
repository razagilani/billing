"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
from core.model import Session, UtilBill, SupplyGroup, Supplier

from upgrade_scripts import alembic_upgrade
from core import init_model

log = logging.getLogger(__name__)

def create_and_assign_supply_groups(s):
    suppliers = s.query(Supplier).all()
    for supplier in suppliers:
        bill = s.query(UtilBill).filter_by(supplier=supplier).first()
        if bill is not None:
            supply_group = SupplyGroup('SOSGroup', supplier, bill.get_service())
        else:
            supply_group = SupplyGroup('SOSGroup', supplier, '')
        bills = s.query(UtilBill).filter_by(supplier=supplier).all()
        for bill in bills:
            bill.supply_group = supply_group
        s.add(supply_group)


def upgrade():
    log.info('Beginning upgrade to version 27')

    init_model(schema_revision='100f25ab057f')
    s = Session()

    log.info('upgrading to 44557759112a')
    alembic_upgrade('44557759112a')
    init_model(schema_revision='44557759112a')
    create_and_assign_supply_groups(s)
    s.commit()
