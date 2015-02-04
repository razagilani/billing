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
from pg.pg_model import PGAccount
from upgrade_scripts import alembic_upgrade
import logging
from core import init_model
from core.model.model import Session,UtilityAccount, Charge, RateClass, Utility, UtilBill

log = logging.getLogger(__name__)


def create_pg_accounts(session):
    for ua in session.query(UtilityAccount).filter(
                    UtilityAccount.account >= '20000').all():
        session.add(PGAccount(ua))


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

def copy_service_to_rate_class(session):
    '''copies service from utilbill to rate_class table'''

    for rate_class in session.query(RateClass).all():
        if rate_class.utility_id is not None:
            utilbill = session.query(UtilBill).join(Utility).\
                filter(UtilBill.utility_id==rate_class.utility_id).first()
        log.info('setting rate_class %s service to %s' %(rate_class.name, utilbill.service))
        rate_class.service = utilbill.service

def upgrade():
    log.info('Beginning upgrade to version 24')


    log.info('upgrading schema to revision 5a356721c95e')
    alembic_upgrade('5a356721c95e')
    init_model(schema_revision='5a356721c95e')

    session = Session()
    create_pg_accounts(session)
    mark_charges_as_distribution_or_supply(session)
    copy_service_to_rate_class(session)

    log.info('upgrading schema to revision 2d65c7c19345')
    init_model(schema_revision='5a356721c95e')
    alembic_upgrade('2d65c7c19345')


    session.commit()

