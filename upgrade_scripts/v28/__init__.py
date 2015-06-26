"""Upgrade script for version 28.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from itertools import groupby
import json
import logging
from brokerage.brokerage_model import Company, MatrixQuote, CompanyPGSupplier
from core.model import Session, UtilBill, SupplyGroup, Supplier, Utility, \
    RateClass, AltitudeSession

from alembic.config import Config
import pymongo

from sqlalchemy import create_engine

from upgrade_scripts import alembic_upgrade
from core import init_model, init_altitude_db
from core.model import Session
from reebill.reebill_model import User, ReeBillCustomer
from upgrade_scripts import alembic_upgrade
from core.model import Register
from upgrade_scripts.v27.postgres import migrate_to_postgres


def insert_matrix_file_names(s):
    de = s.query(Supplier).filter_by(name='direct energy').one()
    de.matrix_file_name = 'directenergy.xls'
    aep = s.query(Supplier).filter_by(name='AEP').one()
    aep.matrix_file_name = 'aep.xls'
    usge = s.query(Supplier).filter_by(name='USG&E').one()
    usge.matrix_file_name = 'usge.xls'

def upgrade():
    alembic_upgrade('30597f9f53b9')

    init_model()
    init_altitude_db()
    s, a = Session(), AltitudeSession()

    insert_matrix_file_names(s)
    #s.add_all(a.query(Company).all())
    for supplier in a.query(CompanyPGSupplier).all():
        s.merge(supplier)

    MatrixQuote.__table__.drop(checkfirst=True)
    MatrixQuote.__table__.create()

    s.commit()
    a.commit()
