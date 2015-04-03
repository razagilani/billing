"""Upgrade script for version 26.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import csv
import logging
from billentry.billentry_model import Role
from core.altitude import AltitudeSupplier

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session, Supplier

log = logging.getLogger(__name__)

def create_project_manager_role():
    manager_role = Role('Project Manager',
                        'Role for accessing reports view of billentry app')
    return manager_role

def upgrade():
    log.info('Beginning upgrade to version 26')

    log.info('upgrading to 100f25ab057f')
    alembic_upgrade('100f25ab057f')

    init_model(schema_revision='100f25ab057f')
    s = Session()
    s.add(create_project_manager_role())
    rename_suppliers(s)
    match_supplierswith_altitude_suppliers(s)
    import_altitude_suppliers(s)
    s.commit()

def rename_suppliers(s):
    supplier1 = s.query(Supplier).filter_by(id=2).first()
    assert supplier1.name == 'washington gas'
    supplier1.name = 'WGL'
    supplier2 = s.query(Supplier).filter_by(id=6).first()
    assert supplier2.name == 'dominion'
    supplier2.name = 'Dominion Energy Solutions'

def match_supplierswith_altitude_suppliers(s):
    supplier = s.query(Supplier).filter_by(id=2).first()
    altitude_supplier = AltitudeSupplier(supplier, '2ac56bff-fb88-4ac8-8b7f-f97b903750f4')
    s.add(altitude_supplier)
    supplier = s.query(Supplier).filter_by(id=14).first()
    altitude_supplier = AltitudeSupplier(supplier, 'e2830d1f-a59f-49d5-b445-35ccc9ddf036')
    s.add(altitude_supplier)
    supplier = s.query(Supplier).filter_by(id=9).first()
    altitude_supplier = AltitudeSupplier(supplier, '91f09f4a-7d11-41c9-a368-aa586d5d53eb')
    s.add(altitude_supplier)

def import_altitude_suppliers(s):
    with open('upgrade_scripts/v26/utilities.csv', 'r') as csvfile:
        reader = csv.reader(csvfile, delimiter=',')
        existing_guids = ['2ac56bff-fb88-4ac8-8b7f-f97b903750f4',
            'e2830d1f-a59f-49d5-b445-35ccc9ddf036',
            '91f09f4a-7d11-41c9-a368-aa586d5d53eb']
        for row in reader:
            if row[2] == '4' and row[1] not in existing_guids:
                supplier = Supplier(row[0])
                altitude_supplier = AltitudeSupplier(supplier, row[1])
                s.add(altitude_supplier)





