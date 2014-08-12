"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.schema import MetaData, Table
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.processing.state import Session, Company, Customer, Utility, \
    Address

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


def read_initial_customer_data(session):
    meta = MetaData()
    customer_table = Table('customer', meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([customer_table]))
    return {row['id']: row for row in result}


def create_utilities(session):
    for utility_name in utility_names:
        empty_address = Address('', '', '', '', '')
        utility_company = Utility(utility_name, empty_address)
        session.add(utility_company)
    session.flush()

def migrate_customer_fb_utilbill(customer_data, session):
    company_map = {c.name.lower(): c for c in session.query(Company).all()}
    for customer in session.query(Customer).all():
        fb_utility_name = customer_data[customer.id]['fb_utility_name'].lower()
        log.debug('Setting fb_utility to %s for customer id %s' %
                  (fb_utility_name, customer.id))
        try:
            customer.fb_company = company_map[fb_utility_name]
        except KeyError:
            log.error("Could not locate company with name '%s' for customer %s" %
                      (fb_utility_name, customer.id))


def upgrade():
    log.info('Beginning upgrade to version 23')

    log.info('Upgrading schema to revision fc9faca7a7f')
    alembic_upgrade('fc9faca7a7f')

    init_model(schema_revision='fc9faca7a7f')

    session = Session()
    log.info('Reading initial customers data')
    customer_data = read_initial_customer_data(session)
    log.info('Creating utilities')
    create_utilities(session)
    log.info('Migrating customer fb utilbill')
    migrate_customer_fb_utilbill(customer_data, session)
    log.info('Committing to database')
    session.commit()

    log.info('Upgrading schema to revision 18a02dea5969')
    alembic_upgrade('18a02dea5969')
    log.info('Upgrade to version 23 complete')
