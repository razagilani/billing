"""Upgrade script for version 23.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.
"""
from boto.s3.connection import S3Connection
from billing.pg.pg_model import PGAccount
from upgrade_scripts import alembic_upgrade
import logging
from billing import config, init_model
from billing.core.model.model import Session, Customer, Utility, \
    Address, UtilBill, Supplier, RateClass, UtilityAccount

log = logging.getLogger(__name__)


def create_pg_accounts(session):
    for ua in session.query(UtilityAccount).filter(
                    UtilityAccount.account >='20000').all():
        session.add(PGAccount(ua))

def upgrade():
    log.info('Beginning upgrade to version 24')

    alembic_upgrade('556352363426')

    init_model(schema_revision='556352363426')
    session = Session()
    create_pg_accounts(session)

    session.commit()

