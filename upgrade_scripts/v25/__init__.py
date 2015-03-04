"""Upgrade script for version 25.

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
from core.model import Session,UtilityAccount, Charge, RateClass, \
    Address, UtilBill, Supplier, RateClass, UtilityAccount, Charge, Register
from brokerage.brokerage_model import BrokerageAccount

log = logging.getLogger(__name__)


def upgrade():
    log.info('Beginning upgrade to version 25')

    log.info('Upgrading schema to revision 150d8bb1183c')
    alembic_upgrade('150d8bb1183c')

    init_model(schema_revision='150d8bb1183c')
    s = Session()

    s.commit()
