"""Upgrade script for version 22.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
import datetime
import logging

from bson.errors import InvalidId
from sqlalchemy.sql.schema import MetaData, Table
from sqlalchemy.sql import select
from pymongo import MongoClient
from bson.objectid import ObjectId

from upgrade_scripts import alembic_upgrade
from billing import config, init_model
from billing.core.model import (Session, Register, UtilBill, Address, Customer,
        MYSQLDB_DATETIME_MIN, Charge)
from billing.reebill.state import ReeBill, Payment


log = logging.getLogger(__name__)

client = MongoClient(config.get('mongodb', 'host'),
                    int(config.get('mongodb', 'port')))
db = client[config.get('mongodb', 'database')]


def read_initial_customer_data(session):
    log.info('Reading initial customers data before schema migration')
    meta = MetaData()
    customer_table = Table('customer', meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([customer_table]))
    return {row['id']: row for row in result}

def set_fb_attributes(initial_customer_data, session):
    for customer in session.query(Customer).all():
        template_id = \
            str(initial_customer_data[customer.id]['utilbill_template_id'])
        log.debug('Looking up fb attributes for customer id %s having template'
                  ' utilbill document id "%s"' % (customer.id, template_id))

        try:
            template_ub = db.utilbills.find_one({"_id": ObjectId(template_id)})
        except InvalidId:
            template_ub = None

        if template_ub is None:
            log.error('Unable to locate template utilbill with id "%s"' %
                      template_id)
            continue

        a = template_ub['billing_address']
        customer.fb_billing_address = Address(a['addressee'], a['street'],
                                        a['city'], a['state'], a['postal_code'])
        log.debug('Added fb_billing_address %s for customer id %s' %
                  (a, customer.id))

        a = template_ub['service_address']
        customer.fb_service_address = Address(a['addressee'], a['street'],
                                        a['city'], a['state'], a['postal_code'])
        log.debug('Added fb_service_address %s for customer id %s' %
                  (a, customer.id))

        customer.fb_rate_class = template_ub['rate_class']
        log.debug('Adding fb_rate_class %s for customer id %s' %
                  (template_ub['rate_class'], customer.id))

        customer.fb_utility_name = template_ub['utility']
        log.debug('Adding fb_utility_name %s for customer id %s' %
                  (template_ub['utility'], customer.id))

def copy_registers_from_mongo(s):
    log.info('Copying registers from Mongo')
    assert s.query(Register).first() is None, "Registers table is not empty"

    for ub in s.query(UtilBill).all():
        mongo_ub = db.utilbills.find_one({"_id": ObjectId(ub.document_id)})
        if mongo_ub is None:
            if ub.state != UtilBill.Hypothetical:
                log.error("No mongo utility bill found for utilbill"
                          "   id %s document_id %s" % (ub.id, ub.document_id))
            continue

        for mongo_meter in mongo_ub['meters']:
            for mongo_register in mongo_meter['registers']:
                #log.debug('Adding register for utilbill id %s' % ub.id)
                s.add(Register(ub,
                               mongo_register.get('description', ""),
                               mongo_register.get('identifier', ""),
                               mongo_meter.get('estimated', False),
                               mongo_register.get('type', ""),
                               None, #active_periods does not exist in Mongo
                               mongo_meter.get('identifier', ""),
                               quantity=mongo_register.get('quantity', 0),
                               quantity_units=mongo_register.get('quantity_units', ""),
                               register_binding=mongo_register.get('register_binding', "")))

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

def assign_reebill_id_to_payments(s):

    for reebill in s.query(ReeBill).filter(ReeBill.issued == 1).all():
        if reebill.sequence == 1:
            reebill.total_adjustment = 0

            # include all payments since the beginning of time, in case there
            # happen to be any.
            # if any version of this bill has been issued, get payments up
            # until the issue date; otherwise get payments up until the
            # present.
            present_v0_issue_date = reebill.issue_date
            if present_v0_issue_date is None:
                payments = s.query(Payment).filter(Payment.customer==s.query(Customer).filter(Customer.id==reebill.customer_id).one())\
                    .filter(Payment.date_applied < datetime.utcnow)\
                    .filter(Payment.date_applied >= MYSQLDB_DATETIME_MIN).all()
                for payment in payments:
                    payment.reebill_id = reebill.id
            else:
                payments = s.query(Payment).filter(Payment.customer==s.query(Customer).filter(Customer.id==reebill.customer_id).one())\
                    .filter(Payment.date_applied < present_v0_issue_date)\
                    .filter(Payment.date_applied >= MYSQLDB_DATETIME_MIN).all()
                for payment in payments:
                    payment.reebill_id = reebill.id
        else:
            account = s.query(Customer).filter(Customer.id==reebill.customer_id).one().account
            predecessor = s.query(ReeBill).join(Customer) \
                    .filter(Customer.account == account) \
                    .filter(ReeBill.sequence == reebill.sequence - 1) \
                    .filter(ReeBill.version == 0).one()
            if predecessor.issued:
                # if predecessor's version 0 is issued, gather all payments from
                # its issue date until version 0 issue date of current bill, or
                # today if this bill has never been issued
                if s.query(ReeBill).join(Customer) \
                            .filter(Customer.account == account) \
                            .filter(ReeBill.sequence == reebill.sequence) \
                            .filter(ReeBill.version == 0).one().issued:
                    present_v0_issue_date = s.query(ReeBill).join(Customer) \
                            .filter(Customer.account == account) \
                            .filter(ReeBill.sequence == reebill.sequence) \
                            .filter(ReeBill.version == 0).one().issue_date
                    payments = s.query(Payment).filter(Payment.customer_id==reebill.customer_id)\
                            .filter(Payment.date_applied < present_v0_issue_date)\
                            .filter(Payment.date_applied >= predecessor.issue_date).all()
                    for payment in payments:
                        payment.reebill_id = reebill.id
                else:
                    payments = s.query(Payment).filter(Payment.customer_id==reebill.customer_id)\
                            .filter(Payment.date_applied < datetime.utcnow())\
                            .filter(Payment.date_applied >= predecessor.issue_date).all()
                    for payment in payments:
                        payment.reebill_id = reebill.id

def set_customer_service_type(s):
    for customer in s.query(Customer).all():
        if customer.account.startswith('1'):
            if customer.account in ('10160', '10161'):
                customer.service = 'pv'
            else:
                customer.service = 'thermal'
        else:
            customer.service = None

def fill_in_charges_quantity_units(s):
    for charge in s.query(Charge).all():
        if charge.quantity_units in (None, '', 'None', 'Therms'):
            if charge.utilbill.service == 'gas':
                charge.quantity_units = 'therms'
            elif charge.utilbill.service == 'electric':
                charge.quantity_units = 'kWh'
            else:
                # replace None with '' because at least it's non-null
                charge.utilbill.service = '';
        elif charge.quantity_units.lower() == 'ccf':
            charge.quantity_units = 'therms'
        # how could these ever have worked?
        elif charge.quantity_units == 'REG_TOTAL.quantityunits':
            charge.quantity_units = 'therms'
        elif charge.quantity_units == 'Unit':
            charge.quantity_units = 'dollars'

def upgrade():
    log.info('Beginning upgrade to version 22')

    log.info('Upgrading to schema revision 32bbb4189c1')
    alembic_upgrade('32bbb4189c1')
    log.info('Alembic Upgrade Complete')

    init_model(schema_revision='32bbb4189c1')

    session = Session()
    set_customer_service_type(session)
    log.info('Reading initial customer info')
    initial_customer_data = read_initial_customer_data(session)
    log.info('Setting fb attributes')
    set_fb_attributes(initial_customer_data, session)
    log.info('Copying registers from mongo')
    copy_registers_from_mongo(session)
    log.info('Copying RSIs from mongo')
    copy_rsis_from_mongo(session)
    log.info('Filling in missing values for charge.quantity_units')
    fill_in_charges_quantity_units(session)
    log.info('Committing data migration to database')
    session.commit()

    log.info('Upgrading to schema revision 2e47f4f18a8b')
    alembic_upgrade('2e47f4f18a8b')

    log.info('Upgrading to schema revision 6446c51511c')
    alembic_upgrade('6446c51511c')

    log.info('Setting reebill_ids in payments for issued reebills')
    assign_reebill_id_to_payments(session)
    session.commit()

    log.info('Upgrade to version 22 complete')
