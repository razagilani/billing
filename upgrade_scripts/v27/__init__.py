"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import json
import logging
from core.model import Session, UtilBill, SupplyGroup, Supplier

from alembic.config import Config
import pymongo

from sqlalchemy import create_engine

from upgrade_scripts import alembic_upgrade
from core import init_model
from core.model import Session
from reebill.reebill_model import User, ReeBillCustomer
from upgrade_scripts import alembic_upgrade
from core.model import Register
from upgrade_scripts.v27.postgres import migrate_to_postgres


REVISION = '58383ed620d3'

log = logging.getLogger(__name__)

def create_and_assign_supply_groups(s):
    suppliers = s.query(Supplier).all()
    for supplier in suppliers:
        bill = s.query(UtilBill).filter_by(supplier=supplier).first()
        # if there is a bill for a supplier then create a supply group by
        # naming it as bill.utility.name + ' SOS' otherwise don't create
        # a supply group
        if bill is None:
            continue
        supply_group = SupplyGroup(bill.utility.name + ' SOS', supplier, bill.get_service())
        bill.utility.sos_supply_group = supply_group
        bills = s.query(UtilBill).filter_by(supplier=supplier).all()
        for bill in bills:
            bill.supply_group = supply_group
            bill.utility_account.supply_group = supply_group
        s.add(supply_group)



def migrate_users(s):
    from core import config
    host = config.get('mongodb', 'host')
    port = config.get('mongodb', 'port')
    db_name = config.get('mongodb', 'database')
    log.info('Migrating %s.users from MongoDB' % db_name)
    con = pymongo.Connection(host=host, port=port)
    db = con[db_name]
    for mongo_user in db.users.find():
        log.info('Copying user %s' % mongo_user['_id'])
        user = User(username=mongo_user['name'],
                    identifier=mongo_user['_id'],
                    _preferences=json.dumps(mongo_user['preferences']),
                    password_hash=mongo_user['password_hash'],
                    salt=mongo_user['salt'],
                    session_token=mongo_user.get('session_token', None))
        s.add(user)

def set_payee_for_reebill_customers(s):
    reebill_customers = s.query(ReeBillCustomer).all()
    for customer in reebill_customers:
        customer.payee = 'Nextility'


def upgrade():
    log.info('Beginning upgrade to version 27')

    from core import config
    old_uri = config.get('db', 'old_uri')
    new_uri = config.get('db', 'uri')
    assert old_uri.startswith('mysql://')
    assert new_uri.startswith('postgresql://')
    old_db_config = Config('alembic.ini')
    old_db_config.set_main_option("sqlalchemy.url", old_uri)
    
    alembic_upgrade('a583e412020')

    log.info('Cleaning up reading.register_binding values')
    # clean up reading.register_binding before changing the column type.
    # this enables converting reading.register_binding to the same type as
    # register.register_binding to enable comparisons.
    mysql_engine = create_engine(old_uri)
    mysql_engine.execute(
        "update reading set register_binding = 'REG_TOTAL' where "
        "register_binding is null or register_binding in ('None', '')"
        "or register_binding not in %s" % str(
            tuple(Register.REGISTER_BINDINGS)))

    log.info('Upgrading schema to revision %s' % REVISION)
    alembic_upgrade(REVISION, config=old_db_config)

    init_model(uri=old_uri, schema_revision=REVISION)

    s = Session()
    migrate_users(s)
    set_payee_for_reebill_customers(s)
    create_and_assign_supply_groups(s)
    s.commit()

    log.info('Migrating to PostgreSQL')
    migrate_to_postgres(old_db_config, old_uri, new_uri)