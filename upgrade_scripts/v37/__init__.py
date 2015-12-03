"""Upgrade script for version 27.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
import os
import subprocess

from core.model import Session, AltitudeSession
from core import init_model, get_db_params, init_altitude_db
from upgrade_scripts import alembic_upgrade

log = logging.getLogger(__name__)

def upgrade():
    alembic_upgrade('4f589e8d4cab')

    init_model()
    s = Session()
    s.commit()
