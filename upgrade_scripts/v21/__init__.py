"""Upgrade script for version 21. 

Script must define `upgrade`, the function for upgrading.

Important: For the purpose of allowing schema migration, this module will be 
imported with the data model uninitialized! Therefore this module should not 
import any other code that that expects an initialized data model without first
calling :func:`.billing.init_model`.  
"""
from upgrade_scripts import alembic_upgrade
import logging
from billing import init_model

log = logging.getLogger(__name__)

def upgrade():
    log.info('Beginning upgrade to version 21')
    alembic_upgrade('55e7e5ebdd29')
    init_model()
    
    ##Code to copy data from mongo goes here

    
    log.info('Upgrade to version 21 complete')
