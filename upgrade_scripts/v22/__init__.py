"""Upgrade script for version 22.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from sqlalchemy.engine import create_engine
from sqlalchemy.sql.schema import MetaData, Table
from sqlalchemy.sql import select
from upgrade_scripts import alembic_upgrade
import logging
from pymongo import MongoClient
from billing import config, init_model
from billing.processing.state import Session, Charge
from billing.processing.rate_structure2 import RateStructureDAO
from processing.state import Register, UtilBill, Address, Customer
from bson.objectid import ObjectId

log = logging.getLogger(__name__)

client = MongoClient(config.get('billdb', 'host'),
    int(config.get('billdb', 'port')))
db = client[config.get('billdb', 'database')]



# def previous_session():
#     from state_from_v21 import Session, Base, check_schema_revision
#     from sqlalchemy import create_engine
#
#     uri = config.get('statedb', 'uri')
#     log.debug('Intializing v21 sqlalchemy model with uri %s' % uri)
#     engine = create_engine(uri)
#     Session.configure(bind=engine)
#     Base.metadata.bind = engine
#     check_schema_revision()
#     return Session


def read_initial_customer_data(session):
    log.info('Reading initial customers data before schema migration')
    meta = MetaData()
    customer_table = Table('customer', meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([customer_table]))
    print result.keys()
    return {row['document_id']: row for row in result}

def set_fb_attributes(initial_customer_data, session):
    utilbill_map = {ub.id: ub for ub in session.query(UtilBill).all()}
    for customer in session.query(Customer).all():
        template_utilbill_id = \
            initial_customer_data[customer.id]['utilbill_template_id']
        log.debug('Looking up fb attributes for customer id %s having template'
                  ' utilbill id "%s"' % (customer.id, template_utilbill_id))
        try:
            template_utilbill = utilbill_map[template_utilbill_id]
        except KeyError:
            log.error('Unable to locate template utilbill with id "%s"' %
                      template_utilbill_id)
            continue

        customer.fb_billing_address = template_utilbill.billing_address
        customer.fb_service_address = template_utilbill.service_address
        customer.fb_rate_class = template_utilbill.rate_class
        customer.fb_utility_name = template_utilbill.utility
    exit()

def copy_registers_from_mongo(s):
    log.info('Copying registers from Mongo')
    assert s.query(Register).first() is None, "Registers table is not empty"

    for ub in s.query(UtilBill).all():
        mongo_ub = db.utilbills.find_one({"_id": ObjectId(ub.document_id)})
        if mongo_ub is None:
            log.error("No mongo utility bill found for utilbill"
                      "   id %s document_id %s" % (ub.id, ub.document_id))
            continue

        for mongo_meter in mongo_ub['meters']:
            for mongo_register in mongo_meter['registers']:
                #log.debug('Adding register for utilbill id %s' % ub.id)
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

def copy_rsis_from_mongo(s):
    for u in s.query(UtilBill).all():
        rs = db.ratestructure.find_one({'_id': ObjectId(u.uprs_document_id)})
        if rs is None:
            log.error('utilbill id %s: missing RS document with id %s' % (
                    u.id, u.uprs_document_id))
            continue
        for charge in u.charges:
            #log.debug('Updating charge id %s for utilbill id %s' % (
                    #charge.id, u.id))
            try:
                rsi = next(r for r in rs['rates'] if r['rsi_binding'] ==
                        charge.rsi_binding)
            except StopIteration:
                log.error('utilbill id %s charge id %s: no RSI %s %s' % (
                        u.id, charge.id, charge.rsi_binding,
                        [r['rsi_binding'] for r in rs['rates']]))
                # a utility bill with messed-up formulas should not be used for
                # generating new bills' charges
                u.processed = False
                continue
            charge.quantity_formula = rsi['quantity']
            charge.rate_formula = rsi['rate']
            charge.roundrule = rsi.get('roundrule', '')
            charge.shared = rsi.get('shared', True)
            charge.has_charge = rsi.get('has_charge', True)

def upgrade():
    log.info('Beginning upgrade to version 22')
    log.info('Upgrading to schema revision 39efff02706c')
    alembic_upgrade('39efff02706c')
    log.info('Alembic Upgrade Complete')
    init_model(schema_revision='39efff02706c')
    session = Session()

    log.info('Reading initial customer info')
    initial_customer_data = read_initial_customer_data(session)
    log.info('Setting fb attributes')
    set_fb_attributes(initial_customer_data, session)
    log.info('Copying registers from mongo')
    copy_registers_from_mongo(session)
    log.info('Copying RSIs from mongo')
    copy_rsis_from_mongo(session)
    log.info('Committing to database')
    session.commit()

    log.info('Upgrading to schema revision 2e47f4f18a8b')
    alembic_upgrade('2e47f4f18a8b')
    log.info('Upgrade to version 22 complete')

    """


    try:
        alembic_upgrade(connection, '39efff02706c')
        log.info('Alembic Upgrade Complete')
        init_model(schema_revision='39efff02706c')
        s = Session(bind=connection)

        set_fb_attributes(initial_customer_data, s)
        copy_registers_from_mongo(s)
        copy_rsis_from_mongo(s)
    except:
        transaction.rollback()
        raise


    transaction.rollback()

    #log.info('Committing to database')
    #s.commit()
    #log.info('Upgrade to version 22 complete')
    """