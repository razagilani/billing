"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from boto.s3.connection import S3Connection
from sqlalchemy import func, distinct
from sqlalchemy.sql.expression import select
from sqlalchemy.sql.schema import MetaData, Table
from reebill.state import Reading, ReeBillCharge
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.core.model.model import Session, Company, Customer, Utility, \
    Address, UtilBill, Supplier, RateClass, Charge
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


def clean_up_units(session):
    # get rid of nulls to prepare for other updates
    for table, col in [
        ('register', 'quantity_units'),
        ('charge', 'quantity_units'),
        ('reading', 'unit'),
        ('reebill_charge', 'quantity_unit'),
    ]:
        session.execute('update %(table)s set %(col)s = "" where %(col)s '
                        'is null' % dict(table=table, col=col))


    # for charges, default unit is "dollars"
    command = ('update %(table)s '
               'set %(col)s = "%(newvalue)s" where %(col)s = "%(oldvalue)s" ')
    for table, col in [
        ('charge', 'quantity_units'),
        ('reebill_charge', 'quantity_unit'),
    ]:
        session.execute(command % dict(table=table, col=col, oldvalue='',
                                       newvalue='dollars', condition=''))

    # replace many nonsensical units with a likely unit for the given bill,
    # either therms or kWh depending on energy type. also "ccf" should
    # replaced by therms, and variant names for the same unit should be
    # corrected.
    command = ('update %(table)s %(join)s '
               'set %(col)s = "%(newvalue)s" where %(col)s = "%(oldvalue)s" '
               '%(condition)s')
    for table, col in [
        ('register', 'quantity_units'),
        ('reading', 'unit'),
        ('charge', 'quantity_units'),
        ('reebill_charge', 'quantity_unit'),
    ]:
        params = dict(table=table, col=col, condition='')
        if table in ('reading', 'reebill_charge'):
            params['join'] = ('join reebill on %s.reebill_id = reebill.id '
                'join utilbill_reebill '
                'on reebill.id = utilbill_reebill.reebill_id '
                'join utilbill on utilbill_reebill.utilbill_id = utilbill.id '
                % table)
        else:
            params['join'] = 'join utilbill on utilbill_id = utilbill.id'
        session.execute(command % dict(params, oldvalue='Ccf',
                                       newvalue='therms'))
        session.execute(command % dict(params, oldvalue='kW', newvalue='kWD'))
        session.execute(command % dict(params, oldvalue='KWD', newvalue='kWD'))
        for invalid_unit in [
            '',
            'REG_TOTAL.quantityunits',
            'Unit',
            'Therms',
            'None',
        ]:
            session.execute(command % dict(params, oldvalue=invalid_unit,
                                           newvalue='therms',
                                           condition='and service = "gas"'))
            session.execute(command % dict(params, oldvalue=invalid_unit,
                                           newvalue='kWh',
                                           condition='and service = "electric"'))

    # check that all resulting units are valid
    valid_units = [
        'kWh',
        'dollars',
        'kWD',
        'therms',
        'MMBTU',
    ]
    for table, col in [
        ('register', 'quantity_units'),
        ('charge', 'quantity_units'),
        ('reading', 'unit'),
        ('reebill_charge', 'quantity_unit'),
    ]:
        values = list(x[0] for x in session.execute(
                'select distinct %s from %s' % (col, table)))
        assert all(v in valid_units for v in values)
    session.commit()

def read_initial_table_data(table_name, session):
    meta = MetaData()
    table = Table(table_name, meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([table]))
    return {row['id']: row for row in result}

def create_utilities(session):
    bill_utilities = session.execute("select distinct utility from utilbill");
    for bill_utility in bill_utilities:
        empty_address = Address('', '', '', '', '')
        empty_guid = ''
        utility_company = Utility(bill_utility['utility'], empty_address, empty_guid)
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
        utility_name = utilbill_data[utility_bill.id]['utility'].lower()
        '''if utilbill_data[utility_bill.id]['utility'].lower()!='washgas' \
            else 'Washington Gas'.lower()'''
        log.debug('Setting utility to %s for utilbill id %s' %
                  (utility_name, utility_bill.id))
        try:
            utility_bill.utility = company_map[utility_name]
            if utility_bill.utility.name == 'washgas':
                utility_bill.utility.name = 'washington gas'
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
    session.commit()

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

def create_rate_classes(session):
    utilbills = session.execute("select distinct rate_class, utility_id from utilbill")

    for bill in utilbills:
        log.debug('Creating RateClass object with name %s and utility_id %s'
                  %(bill['rate_class'], bill['utility_id']))
        utility = session.query(Utility).filter(Utility.id==bill['utility_id']).one()
        rate_class = RateClass(bill['rate_class'], utility)
        session.add(rate_class)
    session.flush()
    session.commit()

def set_rate_class_ids(session, utilbill_data, customer_data):
    utilbills = session.query(UtilBill).all()
    for bill in utilbills:
        u_rate_class = session.query(RateClass).join(UtilBill, RateClass.utility_id==bill.utility_id).\
            filter(RateClass.name==utilbill_data[bill.id]['rate_class']).first()
        log.debug('setting rate_class_id to %s for utilbill with id %s'
                  %(u_rate_class.id, bill.id))
        bill.rate_class_id = u_rate_class.id
    customers = session.query(Customer).all()
    for customer in customers:
        c_rate_class = session.query(RateClass).join(Customer, RateClass.utility_id==customer.fb_utility_id).\
            filter(RateClass.name==customer_data[customer.id]['fb_rate_class']).first()
        if c_rate_class is None:
            customer.fb_rate_class_id = Session.query(RateClass).first().id
        else:
            log.debug('setting rate_class_id to %s for customer with id %s'
                  %(c_rate_class.id, customer.id))
            customer.fb_rate_class_id = c_rate_class.id

def delete_hypothetical_utility_bills(session):
    # UtilBill.Hypothetical == 3, but that name can't be used because it
    # has been removed from the code
    session.query(UtilBill).filter_by(state=3).delete()

def upgrade():
    cf = config.get('aws_s3', 'calling_format')
    log.info('Beginning upgrade to version 23')

    init_model(schema_revision='6446c51511c')
    session = Session()
    clean_up_units(session)
    alembic_upgrade('37863ab171d1')

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

    #log.info('Uploading utilbills to AWS')
    #upload_utilbills_to_aws(session)

    log.info('Setting up fb_utility_id')
    set_fb_utility_id(session)

    log.info('setting up supplier ids')
    set_supplier_ids(session)

    log.info('Committing to database')
    session.commit()

    log.info('Upgrading schema to revision 18a02dea5969')
    alembic_upgrade('18a02dea5969')

    log.info('Upgrading schema to revision 3566e62e7af3')
    alembic_upgrade('3566e62e7af3')


    log.info('creating rate_classes')
    create_rate_classes(session)

    log.info('setting up rate_class ids for Customer an UtilBill records')
    set_rate_class_ids(session, utilbill_data, customer_data)

    delete_hypothetical_utility_bills(session)

    log.info('Comitting to Database')
    session.commit()

    log.info('Upgrading to schema 4bc721447593')
    alembic_upgrade('4bc721447593')

    log.info('Upgrade Complete')


