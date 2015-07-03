"""Upgrade script for version 21.
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
from processing.state import Charge, UtilBill, Address, ReeBill
from bson.objectid import ObjectId

log = logging.getLogger(__name__)


def copy_charges_from_mongo():

    client = MongoClient(config.get('billdb', 'host'),
                         int(config.get('billdb', 'port')))
    db = client[config.get('billdb', 'database')]
    s = Session()
    assert s.query(Charge).all() == [], "Charges table is not empty"
    
    for ub in s.query(UtilBill).all():
        mongo_ub = db.utilbills.find_one({"_id": ObjectId(ub.document_id)})
        if mongo_ub is None:
            log.error("No mongo utility bill found for utilbill"
                      "   id %s document_id %s" % (ub.id, ub.document_id))
            continue
        for prop in ['service_address', 'billing_address']:
            log.debug("Adding %s for utilbill id %s" % (prop, ub.id))
            a = mongo_ub[prop]
            setattr(ub, prop, Address(a['addressee'], a['street'], a['city'],
                                      a['state'], a['postal_code']))

        for mongo_charge in mongo_ub['charges']:
            log.debug('Adding charge for utilbill id %s' % ub.id)
            quantity_units = mongo_charge.get('quantity_units', "")
            s.add(Charge(ub,
                         mongo_charge.get('description', ""),
                         mongo_charge.get('group', ""),
                         mongo_charge.get('quantity', 0),
                         quantity_units if quantity_units is not None else '',
                         mongo_charge.get('rate', 0),
                         mongo_charge.get('rsi_binding', ""),
                         mongo_charge.get('total', 0)))
    log.info('Committing to database')
    s.commit()

def set_processed():
    s= Session()
    for reebill in s.query(ReeBill).all():
        reebill.processed = reebill.issued
    log.info("Committing updates to ReeBill.processed to databases")
    s.commit()

def upgrade():
    log.info('Beginning upgrade to version 21')
    alembic_upgrade('3147aa982e03')
    init_model()
    copy_charges_from_mongo()
    set_processed()
    log.info('Upgrade to version 21 complete')
