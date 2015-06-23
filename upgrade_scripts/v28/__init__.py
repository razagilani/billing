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
from core.model import Session, UtilBill, SupplyGroup, Supplier, Utility, \
    RateClass

from alembic.config import Config
import pymongo

from sqlalchemy import create_engine

from upgrade_scripts import alembic_upgrade
from core import init_model
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

def upgrade():
    alembic_upgrade('41bb5135c2b6')

    init_model()
    s = Session()

    insert_matrix_file_names(s)

    s.commit()
