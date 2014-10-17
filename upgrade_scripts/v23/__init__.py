"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from boto.s3.connection import S3Connection
from sqlalchemy import func
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.schema import MetaData, Table
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.core.model.model import Session, Company, Customer, Utility, \
    Address, UtilBill, Supplier
from billing.upgrade_scripts.v23.migrate_to_aws import upload_utilbills_to_aws

log = logging.getLogger(__name__)

client = MongoClient(config.get('mongodb', 'host'),
    int(config.get('mongodb', 'port')))
db = client[config.get('mongodb', 'database')]


utility_names = ['Pepco',
                 'Washington Gas',
                 'Piedmont',
                 'Peco',
                 'BGE',
                 'Dominion',
                 'Sempra Energy',
                 'Florida',
                 'ConocoPhillips',
                 'Scana Energy Marketing',
                 'PG&E']


def read_initial_table_data(table_name, session):
    meta = MetaData()
    table = Table(table_name, meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([table]))
    return {row['id']: row for row in result}

def create_utilities(session):
    for utility_name in utility_names:
        empty_address = Address('', '', '', '', '')
        empty_guid = ''
        utility_company = Utility(utility_name, empty_address, empty_guid)
        session.add(utility_company)
    session.flush()
    session.commit()

def migrate_customer_fb_utility(customer_data, session):
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


def migrate_utilbill_utility(utilbill_data, session):
    company_map = {c.name.lower(): c for c in session.query(Company).all()}
    for utility_bill in session.query(UtilBill).all():
        utility_name = utilbill_data[utility_bill.id]['utility'].lower() \
        if utilbill_data[utility_bill.id]['utility'].lower()!='washgas' \
            else 'Washington Gas'.lower()
        log.debug('Setting utility to %s for utilbill id %s' %
                  (utility_name, utility_bill.id))
        try:
            utility_bill.utility = company_map[utility_name]
        except KeyError:
            log.error("Could not locate company with name '%s' for utilbill %s"
                      % (utility_name, utility_bill.id))

def set_fb_utility_id(session):
    for customer in session.query(Customer):
        first_bill = session.query(UtilBill)\
            .filter(UtilBill.customer == customer)\
            .order_by(UtilBill.period_start)\
            .first()
        if first_bill:
            log.debug('Setting fb_utility_id to %s for customer id %s' %
                  (first_bill.utility_id, customer.id))
            customer.fb_utility_id = first_bill.utility_id

def set_supplier_ids(session):
    for company in session.query(Company).all():
        c_supplier = Supplier(company.name, company.address, company.guid)
        session.add(c_supplier)
        session.flush()
        session.refresh(c_supplier)
    for customer in session.query(Customer).all():
        if customer.fb_utility_id:
            utility = session.query(Utility).\
                filter(Utility.id==customer.fb_utility_id).\
                first()
            supplier_id = session.query(Supplier).\
                filter(Supplier.name==utility.name).\
                first().id
            log.debug('Setting supplier_id to %s for customer id %s' %
                  (supplier_id, customer.id))
            customer.fb_supplier_id = supplier_id
    for bill in session.query(UtilBill).all():
        if bill.utility:
            utility_name = bill.utility.name
            supplier = session.query(Supplier).\
                filter(Supplier.name==utility_name).\
                first().id
            log.debug('Setting supplier_id to %s for utility bill id %s' %
                  (supplier, bill.id))
            bill.supplier_id = supplier

def upgrade():

    cf = config.get('aws_s3', 'calling_format')
    log.info('Beginning upgrade to version 23')

    log.info('Upgrading schema to revision fc9faca7a7f')
    alembic_upgrade('fc9faca7a7f')
    init_model(schema_revision='fc9faca7a7f')

    session = Session()
    log.info('Reading initial customers data')
    customer_data = read_initial_table_data('customer', session)
    utilbill_data = read_initial_table_data('utilbill', session)

    log.info('Creating utilities')
    create_utilities(session)

    log.info('Migrating customer fb utilbill')
    migrate_customer_fb_utility(customer_data, session)

    log.info('Migration utilbill utility')
    migrate_utilbill_utility(utilbill_data, session)

    log.info('Uploading utilbills to AWS')
    #upload_utilbills_to_aws(session)

    log.info('Setting up fb_utility_id')
    set_fb_utility_id(session)

    log.info('setting up supplier ids')
    set_supplier_ids(session)

    log.info('Committing to database')
    session.commit()

    log.info('Upgrading schema to revision 3566e62e7af3')
    alembic_upgrade('3566e62e7af3')

    log.info('Upgrade Complete')


