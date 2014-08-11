"""Upgrade script for version 23.

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
from billing.processing.state import Session, Charge
from billing.processing.rate_structure2 import RateStructureDAO
from processing.state import Register, UtilBill, Address, Company
from bson.objectid import ObjectId

log = logging.getLogger(__name__)

client = MongoClient(config.get('billdb', 'host'),
    int(config.get('billdb', 'port')))
db = client[config.get('billdb', 'database')]


utility_names = ['Pepco',
                 'Washgas',
                 'Piedmont',
                 'Peco',
                 'BGE',
                 'Dominion',
                 'Sempra Energy',
                 'Florida',
                 'ConocoPhillips',
                 'Scana Energy Marketing',
                 'PG&E']

def create_utilities(session):
    session.add_all([Company(utility_name, address=None) for utility_name in
                     utility_names])


def migrate_utilbill_companies(session):


def upgrade():
    log.info('Beginning upgrade to version 23')
    alembic_upgrade('1a174da18305')
    log.info('Alembic Upgrade Complete')
    init_model()
    log.info('Running migration for version 23')
    session = Session()
    log.info('Committing to database')
    session.commit()
    log.info('Upgrade to version 23 complete')
