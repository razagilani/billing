"""Contains scripts to be run at deployment time of new releases.

This module contains a submodule for each software version upgrade. Every 
submodule should define its own `upgrade` function, which will run schema 
migration, data migration etc. for the version upgrade.
"""

import logging
from alembic.config import Config
from billing import config
from alembic.command import upgrade
from billing import init_model
import importlib

log = logging.getLogger(__name__)

def run_upgrade(version):
    """Upgrade to a specified version
    
    :param version: the version number of the upgrade
    """
    upmod = importlib.import_module('billing.upgrade_scripts.v%s' % version)
    upmod.upgrade()

def alembic_upgrade(revision_to):
    almcfg = Config("alembic.ini")
    upgrade(almcfg, revision_to)



'''
class UpgradeRunner(object):
    """Encapsulates actions for deployment of a software upgrade.  
    """

    @staticmethod
    def alembic_upgrade(revision):
        """Calls `alembic.command.upgrade` to upgrade to the specified revision.
        
        :param revision: the alembic revision to upgrade to
        """
        log.info('Upgrading to Alembic revision %s' % revision)
        almcfg = Config("alembic.ini")
        upgrade(almcfg, revision)
    
    def __init__(self, version,
                 alembic_revision_from=None,
                 alembic_revision_to=None):
        """Construct a new :class:`.UpgradeRunner`.
        
        :param version: the version number of the upgrade
        :param 
        """
        self.version = version
        self.alembic_revision_from = alembic_revision_from
        self.alembic_revision_to = alembic_revision_to

    def upgrade(self):
        """Runs the software upgrade: First, an Alembic schema revision update
        to `self.alembic_revision`, and then each upgrade function within 
        `self.upgrade_functions`.
        """
        if self.alembic_revision_from and self.alembic_revision_to:
            init_model(schema_revision=self.alembic_revision_from)
            self.alembic_upgrade(self.alembic_revision_to)
            init_model(schema_revision=self.alembic_revision_to)
'''
