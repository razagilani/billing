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

from core.model import Session
from core import init_model, get_db_params

log = logging.getLogger(__name__)

def upgrade():
    # restore data from xbill database backup into billing database
    db_params = get_db_params()
    command = 'python xbill/scripts/destage_xbill.py ' \
              '--DBName %(db)s --DBUser %(user)s' % db_params
    with open(os.devnull) as devnull:
        status_code = subprocess.call(command.split(), stdout=devnull)
    assert status_code == 0

    init_model()
    s = Session()
    s.commit()
