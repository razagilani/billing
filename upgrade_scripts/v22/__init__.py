"""Upgrade script for version 22.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.processing.state import Session
from processing.state import Register, UtilBill, Address
from bson.objectid import ObjectId

log = logging.getLogger(__name__)


def copy_registers_from_mongo():
    log.info('Copying registers from Mongo')
    client = MongoClient(config.get('billdb', 'host'),
                         int(config.get('billdb', 'port')))
    db = client[config.get('billdb', 'database')]

    s = Session()
    assert s.query(Register).first() is None, "Registers table is not empty"

    for ub in s.query(UtilBill).all():
        mongo_ub = db.utilbills.find_one({"_id": ObjectId(ub.document_id)})
        if mongo_ub is None:
            log.error("No mongo utility bill found for utilbill"
                      "   id %s document_id %s" % (ub.id, ub.document_id))
            continue

        for mongo_meter in mongo_ub['meters']:
            for mongo_register in mongo_meter['registers']:
                log.debug('Adding register for utilbill id %s' % ub.id)
                s.add(Register(ub,
                               mongo_register.get('description', ""),
                               mongo_register.get('quantity', 0),
                               mongo_register.get('quantity_units', ""),
                               mongo_register.get('identifier', ""),
                               mongo_meter.get('estimated', False),
                               mongo_register.get('type', ""),
                               mongo_register.get('register_binding', ""),
                               None, #active_periods does not exist in Mongo
                               mongo_meter.get('identifier', "")))
    log.info('Committing to database')
    s.commit()

def upgrade():
    log.info('Beginning upgrade to version 22')
    #alembic_upgrade('39efff02706c')
    log.info('Alembic Upgrade Complete')
    init_model()
    copy_registers_from_mongo()
    log.info('Upgrade to version 22 complete')
