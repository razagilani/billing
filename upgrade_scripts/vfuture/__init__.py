"""Placeholder for upgrade script for future changes not yet merged into
the default branch.

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be
imported with the data model uninitialized! Therefore this module should not
import any other code that that expects an initialized data model without first
calling :func:`.core.init_model`.
"""
import logging
import os
import subprocess

from core.model import Session
from core import init_model, get_db_params

log = logging.getLogger(__name__)

def upgrade():

    init_model()
    s = Session()
    s.commit()
