"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import json
import logging

import pymongo

from core import init_model
from core.model import Session
from reebill.reebill_model import User, ReeBillCustomer
from upgrade_scripts import alembic_upgrade


log = logging.getLogger(__name__)


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

    alembic_upgrade('3e4ceae0f397')

    init_model()
    s = Session()
    migrate_users(s)
    set_payee_for_reebill_customers(s)
    s.commit()