"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from boto.s3.connection import S3Connection
from brokerage.brokerage_model import BrokerageAccount
from upgrade_scripts import alembic_upgrade
import logging
from core import config, init_model
from core.model.model import Session, Utility, \
    Address, UtilBill, Supplier, RateClass, UtilityAccount, Charge

log = logging.getLogger(__name__)


def create_pg_accounts(session):
    for ua in session.query(UtilityAccount).filter(
                    UtilityAccount.account >= '20000').all():
        session.add(BrokerageAccount(ua))


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


def upgrade():
    log.info('Beginning upgrade to version 24')

    alembic_upgrade('572b9c75caf3')

    init_model(schema_revision='572b9c75caf3')
    session = Session()
    create_pg_accounts(session)
    mark_charges_as_distribution_or_supply(session)

    session.commit()

