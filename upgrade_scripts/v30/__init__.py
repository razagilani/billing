"""Upgrade script for version 30.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
from core import init_model, init_altitude_db
from core.model import Session
from upgrade_scripts import alembic_upgrade



def upgrade():
    #alembic_upgrade('')

    init_model()