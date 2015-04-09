"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from time import sleep
from boto.s3.connection import S3Connection
from sqlalchemy.sql.schema import MetaData, Table
from sqlalchemy.sql.expression import select
from upgrade_scripts import alembic_upgrade
import logging
from core import init_model
from core.model.model import Session,UtilityAccount, Charge, RateClass, \
    Address, UtilBill, Supplier, RateClass, UtilityAccount, Charge, Register
from brokerage.brokerage_model import BrokerageAccount

log = logging.getLogger(__name__)


def create_pg_accounts(session):
    for ua in session.query(UtilityAccount).filter(
                    UtilityAccount.account >= '20000').all():
        session.add(BrokerageAccount(ua))

def read_utilbill_data(session):
    meta = MetaData()
    utilbill_table = Table('utilbill', meta, autoload=True,
        autoload_with=session.connection())
    result = session.execute(select([utilbill_table.c.service,
        utilbill_table.c.rate_class_id]))
    return result

def bills_with_service_conflicts(session):
    sql_query1 = "select distinct u.id, u.service, u.rate_class_id from utilbill" \
                " u, utilbill u1 where u.rate_class_id = u1.rate_class_id" \
                " and u.service != u1.service group by u.rate_class_id " \
                "order by u.rate_class_id"
    result1 = session.execute(sql_query1)
    sql_query2 = "select distinct u.id, u.service, u.rate_class_id from utilbill" \
                " u, utilbill u1 where u.rate_class_id = u1.rate_class_id" \
                " and u.service != u1.service order by u.rate_class_id"
    result2 = session.execute(sql_query2)
    return result1, result2.rowcount

def mark_charges_as_distribution_or_supply(session):
    supply = ['supply', 'Supply', 'SUPPLY', 'generation', 'Generation',
        'GENERATION', 'transmission', 'Transmission', 'TRANSMISSION']
    distribution = ['Distribution', 'DISTRIBUTION', 'Delivery',
        'DELIVERY', 'Customer Charge', 'STRIDE', 'EmPower', 'Surcharge']
    supply_count = 0
    distribution_count = 0
    other_count = 0
    for charge in session.query(Charge).all():
        if any(s in charge.group or s in charge.description for s in supply):
            charge.type = 'supply'
            supply_count += 1
        elif any(s in charge.group or s in charge.description for s in distribution):
            charge.type = 'distribution'
            distribution_count += 1
        else:
            # distribution charges in this case probably makes more sense
            # as distribution charges have relatively more sub categories
            charge.type = 'distribution'
            other_count += 1
    print 'Found %s supply charges' % supply_count
    print 'Found %s distribution charges' % distribution_count
    print 'Found %s other charges' % other_count

def print_utilbills_with_conflicting_rate_classes(bills, billscount):
    print '---- rate_classes with conflicting service ----'
    for id, service, rate_class in bills:
        print ('utilbill_id: %s, service: %s, rate_class_id: %s'
               % (id, service, rate_class))
    print '---- rate_classes with conflicting service ----'
    print 'Total number of bills with conflicting service %s' %\
          (billscount)

def copy_service_to_rate_class(utilbill_data, session):
    '''copies service from utilbill to rate_class table'''

    for service, rate_class_id in utilbill_data:
        if rate_class_id is not None:
            rate_class = session.query(RateClass).filter(RateClass.id==rate_class_id).one()
            rate_class.service = service

def add_reg_total(session):
    '''All new bills are required to have a REG_TOTAL register. This makes
    ensures that all the existing brokerage bills have it. A dubious method
    is used to determine what the energy unit should be, but currently
    there is no better way.
    '''
    for u in session.query(UtilBill).join(UtilityAccount).join(BrokerageAccount).all():
        if 'REG_TOTAL' in (r.register_binding for r in u.registers):
            continue
        reg_total = Register(REG_TOTAL, 'kWh'),
        reg_total.utilbill = u
        # TODO will have to be changed to u.get_service()
        # when branch to move service column is merged in
        if u.rate_class is None or u.service == 'electric':
            u.registers.append(reg_total)
        else:
            assert u.service == 'gas'
            reg_total.unit = 'therms'
            u.registers.append(reg_total)
    print 'Added REG_TOTAL to brokerage bills'

def upgrade():
    log.info('Beginning upgrade to version 24')

    log.info('upgrading schema to revision 5a356721c95e')
    alembic_upgrade('5a356721c95e')

    init_model(schema_revision='5a356721c95e')
    session = Session()
    conflicting_service_bills, count = bills_with_service_conflicts(session)
    print_utilbills_with_conflicting_rate_classes(conflicting_service_bills,
                                                  count)

    create_pg_accounts(session)
    add_reg_total(session)
    mark_charges_as_distribution_or_supply(session)
    utilbill_data = read_utilbill_data(session)
    copy_service_to_rate_class(utilbill_data, session)
    session.commit()

    # drop column utilbill.service
    log.info('upgrading schema to revision 2d65c7c19345')
    alembic_upgrade('2d65c7c19345')

