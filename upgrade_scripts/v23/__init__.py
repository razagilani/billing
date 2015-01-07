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
from billing.reebill.state import Payment, ReeBill, ReeBillCustomer
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.core.model.model import Session, Customer, Utility, \
    Address, UtilBill, Supplier, RateClass, UtilityAccount
from billing.reebill.state import ReeBill
from billing.upgrade_scripts.v23.migrate_to_aws import upload_utilbills_to_aws
from billing.upgrade_scripts.v23.clean_up_rate_class_data import clean_up_rate_class_data
from billing.upgrade_scripts.v23.import_alitude_utilities import import_altitude_utilities

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
        utility_company = Utility(bill_utility['utility'], empty_address)
        session.add(utility_company)
    session.flush()
    session.commit()

def create_utility_accounts(session, customer_data):
    customers = session.query(Customer).all()
    for customer in customers:
        if customer.fb_billing_address is None:
            fb_billing_address = Address()
        if customer.fb_service_address is None:
            fb_service_address = Address()
        utility_account = UtilityAccount(customer.name,
                                         customer.account,
                                         customer.fb_utility,
                                         customer.fb_supplier,
                                         customer.fb_rate_class,
                                         fb_billing_address,
                                         fb_service_address)
        utilbills = session.query(UtilBill).join(Customer, UtilBill.customer==customer).all()
        for utilbill in utilbills:
            utilbill.utility_account = utility_account
            utilbill.customer = None
        session.add(utility_account)
        if customer.service is not None:
            reebill_customer = ReeBillCustomer(customer.name,
                                               customer.discountrate,
                                               customer.latechargerate,
                                               customer.service,
                                               customer.bill_email_recipient,
                                               utility_account)
            payments = session.query(Payment).join(Customer, Payment.customer==customer).all()
            for payment in payments:
                payment.reebill_customer = reebill_customer
                #payment.customer = None
            reebills = session.query(ReeBill).join(Customer, ReeBill.customer==customer).all()
            for reebill in reebills:
                reebill.reebill_customer = reebill_customer
                #reebill.customer = None
            session.add(reebill_customer)
        # TODO: why is this necessary?
        customer.fb_rate_class = None
        customer.fb_supplier = None
        customer.fb_billing_address = None
        customer.fb_service_address = None
 #   session.flush()
    session.commit()

def migrate_customer_fb_utility(customer_data, session):
    utility_map = {c.name.lower(): c for c in session.query(Utility).all()}
    for customer in session.query(Customer).all():
        fb_utility_name = customer_data[customer.id]['fb_utility_name'].lower()
        # log.debug('Setting fb_utility to %s for utility_account id %s' %
        #           (fb_utility_name, customer.id))
        try:
            customer.fb_utility = utility_map[fb_utility_name]
        except KeyError:
            log.error("Could not locate company with name '%s' for utility_account %s" %
                      (fb_utility_name, customer.id))


def migrate_utilbill_utility(utilbill_data, session):
    utility_map = {c.name.lower(): c for c in session.query(Utility).all()}
    for utility_bill in session.query(UtilBill).all():
        utility_name = utilbill_data[utility_bill.id]['utility'].lower()
        log.debug('Setting utility to %s for utilbill id %s' %
                  (utility_name, utility_bill.id))
        try:
            utility_bill.utility = utility_map[utility_name]
            if utility_bill.utility.name == 'washgas':
                utility_bill.utility.name = 'washington gas'
        except KeyError:
            log.error("Could not locate company with name '%s' for utilbill %s"
                      % (utility_name, utility_bill.id))

def set_fb_utility_id(session):
    for customer in session.query(Customer):
        first_bill = session.query(UtilBill).join(Customer)\
            .order_by(UtilBill.period_start)\
            .first()
        if first_bill:
            log.debug('Setting fb_utility_id to %s for utility_account id %s' %
                  (first_bill.utility_id, customer.id))
            customer.fb_utility_id = first_bill.utility_id
        else:
            # accounts with no bills should be new ones so they have
            # fb_utility and fb_rate_class
            assert customer.fb_utility_id is not None
            assert customer.fb_rate_class_id is not None
    session.commit()

def set_supplier_ids(session):
    for utility in session.query(Utility).all():
        c_supplier = Supplier(utility.name, utility.address)
        session.add(c_supplier)
        session.flush()
        session.refresh(c_supplier)
    for customer in session.query(Customer).all():
        if customer.fb_utility_id:
            utility = session.query(Utility).\
                filter(Utility.id==customer.fb_utility_id).\
                first()
            supplier = session.query(Supplier).\
                filter(Supplier.name==utility.name).\
                first()
            # log.debug('Setting supplier_id to %s for utility_account id %s' %
            #       (supplier, customer.id))
            customer.fb_supplier = supplier
    for bill in session.query(UtilBill).all():
        if bill.utility:
            utility_name = bill.utility.name
            supplier = session.query(Supplier).\
                filter(Supplier.name==utility_name).\
                first()
            # log.debug('Setting supplier_id to %s for utility bill id %s' %
            #       (supplier, bill.id))
            bill.supplier = supplier

def create_rate_classes(session):
    utilbills = session.execute("select distinct rate_class, utility_id from utilbill")

    for bill in utilbills:
        # '''log.debug('Creating RateClass object with name %s and utility_id %s'
        #           %(bill['rate_class'], bill['utility_id']))'''
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
        # log.debug('setting rate_class_id to %s for utilbill with id %s'
        #           %(u_rate_class.id, bill.id))
        bill.rate_class = u_rate_class
        bill.rate_class_id = u_rate_class.id
    customers = session.query(Customer).all()
    for customer in customers:
        c_rate_class = session.query(RateClass).join(Customer, RateClass.utility_id==customer.fb_utility_id).\
            filter(RateClass.name==customer_data[customer.id]['fb_rate_class']).first()
        if c_rate_class is None:
            customer.fb_rate_class = Session.query(RateClass).first()
            customer.fb_rate_class_id = Session.query(RateClass).first().id
        else:
            # log.debug('setting rate_class_id to %s for utility_account with id %s'
            #       %(c_rate_class.id, customer.id))
            customer.fb_rate_class = c_rate_class
            customer.fb_rate_class_id = c_rate_class.id
    session.commit()

def delete_hypothetical_utility_bills(session):
    # UtilBill.Hypothetical == 3, but that name can't be used because it
    # has been removed from the code
    session.query(UtilBill).filter_by(state=3).delete()

def delete_reebills_with_null_reebill_customer(session):
    session.query(ReeBill).filter(ReeBill.reebill_customer_id==None).delete()

def upgrade():
    cf = config.get('aws_s3', 'calling_format')
    log.info('Beginning upgrade to version 23')

    init_model(schema_revision='6446c51511c')
    session = Session()
    log.info('Reading initial customers data')
    customer_data = read_initial_table_data('customer', session)
    utilbill_data = read_initial_table_data('utilbill', session)
    clean_up_units(session)
    alembic_upgrade('37863ab171d1')

    log.info('Upgrading schema to revision 507c0437a7f8')
    alembic_upgrade('507c0437a7f8')
    init_model(schema_revision='507c0437a7f8')

    session =Session()
    log.info('Creating utilities')
    create_utilities(session)

    log.info('Upgrading to schema 42f84150db03')
    alembic_upgrade('42f84150db03')

    log.info('Migrating utility_account fb utilbill')
    migrate_customer_fb_utility(customer_data, session)

    log.info('Migration utilbill utility')
    migrate_utilbill_utility(utilbill_data, session)

    log.info('Uploading utilbills to AWS')
    upload_utilbills_to_aws(session)

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

    log.info('setting up rate_class ids for Customer and UtilBill records')
    set_rate_class_ids(session, utilbill_data, customer_data)

    delete_hypothetical_utility_bills(session)

    log.info('creating utility_accounts and reebill_customers')
    create_utility_accounts(session, customer_data)

    log.info('Comitting to Database')
    session.commit()

    log.info('Upgrading to schema 32b0a5fe5074')
    alembic_upgrade('32b0a5fe5074')

    log.info('Upgrading to schema 28552fdf9f48')
    alembic_upgrade('28552fdf9f48')

    log.info("Cleaning up rate class data")
    clean_up_rate_class_data(session)

    log.info("deleting reebills with null reebill_customer_id")
    delete_reebills_with_null_reebill_customer(session)

    log.info('Comitting to Database')
    session.commit()

    log.info('Upgrading to 5a6d7e4f8b80')
    alembic_upgrade('5a6d7e4f8b80')

    log.info("Importing altitude utilities")
    import_altitude_utilities(session)

    log.info('Comitting to Database')
    session.commit()

    log.info('Upgrade Complete')


